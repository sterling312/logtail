#!/usr/bin/env python
import os
import re
import logging
import argparse
import redis
import hashlib
import json
from jinja2 import Environment, PackageLoader
from werkzeug.contrib.cache import SimpleCache
from datetime import datetime
from tornado import ioloop, log, autoreload, web, gen, websocket
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from sendemail import GmailHandler
from html import HTML
import req

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('-w', '--worker', default=min(4, cpu_count()), type=int, help='worker count')
parser.add_argument('-l', '--level', default='INFO', help='log level')
parser.add_argument('-g', '--log_path', default=CURRENT_DIR, help='log file path')
parser.add_argument('-k', '--seek', default=0, type=int, help='lines to go back on log file reading')
parser.add_argument('-a', '--address', default='0.0.0.0', help='server address')
parser.add_argument('-p', '--port', default=8000, type=int, help='port number')
parser.add_argument('-t', '--timeout', default=60*60, type=int, help='cache timeout')
parser.add_argument('-s', '--static', default='static', help='static file path')
parser.add_argument('-f', '--file_path', default='templates', help='template file path')
parser.add_argument('-D', '--delete', action='store_true', help='delete current cache')

class UrlHandler(list):
    http = []
    ws = []
    pat = re.compile('[A-Z]+')
    @staticmethod
    def _insert_underline(match):
        return '_'+match.group(0)

    def api(self, cls):
        pattern = self.pat.sub(self._insert_underline, cls.__name__).lower().lstrip('_')
        url = web.URLSpec(r'/api/{}'.format(pattern), cls, name=cls.__name__.lower())
        if cls.visible:
            self.http.append(url.reverse())
        if cls.active:
            self.append(url)
        return cls

    def websocket(self, cls):
        pattern = self.pat.sub(self._insert_underline, cls.__name__).lower().lstrip('_')
        url = web.URLSpec(r'/ws/{}'.format(pattern), cls, name=cls.__name__.lower())
        self.ws.append(url.reverse())
        self.append(url)
        return cls

    def route(self, pattern):
        def register(cls):
            if cls.active:
                self.append(web.URLSpec(pattern, cls, name=cls.__name__.lower()))
            return cls
        return register

class Cron(dict):
    def callback(self, name, time):
        if name in self:
            raise KeyError('cannot have duplicate name for callback')
        def wrap(fn):
            callback = ioloop.PeriodicCallback(fn, time)
            self[name] = callback
            callback
            return fn
        return wrap

    def start(self):
        for name in self:
            self.start_one(name)

    def start_one(self, name):
        self[name].start()

    def stop(self):
        for name in self:
            self.stop_one(name)

    def stop_one(self, name):
        self[name].stop()

    def api_call(self, name, *args, **kwargs):
        task = req.api.api_registry.get(name)
        if task:
            return task(*args, **kwargs)

class BaseHandler(web.RequestHandler):
    use_body = False
    task = None
    active = True
    visible = True
    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')

    @property
    def cache(self):
        return self.application.cache

    @property
    def pool(self):
        return self.application.pool

    @property
    def logger(self):
        return self.application.logger

    @property
    def env(self):
        return self.application.env

    @property
    def key(self):
        if self.use_body:
            return '{}/{}'.format(self.request.uri, self.sha[:20])
        else:
            return '{}/'.format(self.request.uri)

    @property
    def sha(self):
        return hashlib.sha1(self.request.body).hexdigest()

    @property
    def params(self):
        params = {}
        if self.request.arguments:
            params = dict(self.request.arguments)
        if self.request.body:
            params.update(json.loads(self.request.body))
        return params

    def callback(self, future):
        try:
            result = future.result()
            if isinstance(result, (dict, list)):
                result = json.dumps(result)
                self.set_header('Content-Type', 'application/json')
            self.to_cache(self.key, result)
            self.write(result)
        except Exception as e:
            self.logger.error(e)
            self.set_status(500)
        finally:
            self.finish()

    def to_cache(self, key, value):
        try:
            self.cache.set(key, value, self.application.cache_timeout)
        except:
            self.cache.set(key, value)
            self.cache.expire(key, self.application.cache_timeout)

    def from_cache(self, key):
        value = self.cache.get(key)
        try:
            json.loads(value)
            self.set_header('Content-Type', 'application/json')
            self.write(value)
            self.finish()
        except Exception as e:
            self.logger.error(e)
            self.cache.delete(key)
            self.set_status(500)

    def cached_api_call(self):
        self.logger.debug(json.dumps(self.params))
        if self.task and self.task in req.api.api_registry:
            task = req.api.api_registry[self.task]
        else:
            self.write_error(404)
            return
        key = self.key
        if self.cache.exists(key):
            self.from_cache(key)
        else:
            self.logger.info('giving worker {}'.format(key))
            self.pool.submit(task, **self.params).add_done_callback(self.callback)

    def render_template(self, html='embed.html', **kwargs):
        self.write(self.application.env.render_template(html, **kwargs))

    def api_call(self, name, *args, **kwargs):
        task = req.api.api_registry.get(name)
        if task:
            return task(*args, **kwargs)

class BaseWSHandler(websocket.WebSocketHandler):
    cl = None
    @property
    def logger(self):
        return self.application.logger

    @property
    def params(self):
        params = {}
        if self.request.arguments:
            params = dict(self.request.arguments)
        return params

    def api_call(self, name, *args, **kwargs):
        task = req.api.api_registry.get(name)
        if task:
            return task(*args, **kwargs)

    def write_message(self, msg):
        if isinstance(msg, (list, tuple, dict)):
            msg = json.dumps(msg)
        websocket.WebSocketHandler.write_message(self, msg)

    def add_client(self):
        if self not in self.cl:
            self.cl.append(self)

    def remove_client(self):
        if self in self.cl:
            self.cl.remove(self)

    def on_message(self, msg):
        pass # not implemented

    @classmethod
    def broadcast(cls, msg):
        if msg is not None:
            for cl in cls.cl:
                cl.write_for_subscription(msg)

    def write_for_subscription(self, msg):
        self.write_message(msg)

class MainServer(web.Application):
    def __init__(self, args, cache):
        self.cache_timeout = args.timeout
        self.cache = cache
        if args.delete:
            self.clear_cache()
        self.pool = ProcessPoolExecutor(args.worker)
        debug = logging.root.level==logging.DEBUG
        self.static = args.static if args.static.startswith('/') else os.path.join(CURRENT_DIR, args.static)
        static = [(r'/static/(.*)', req.CachelessStaticHandler, {'path': self.static})]
        self.env = HTML('data_server', args.file_path)
        web.Application.__init__(self, handlers=req.url_handlers+static, default_host='', debug=debug)
        self.listen(port=args.port, address=args.address)
        self.cron = req.cron
        self.logger = log.app_log
        req.api.stream.path = args.log_path
        req.api.stream.seek = -abs(args.seek)

    def start_cron(self):
        self.cron.start()

    def clear_cache(self):
        if hasattr(self.cache, 'flushdb'):
            self.cache.flushdb()
        elif hasattr(self.cache, '_cache'):
            self.cache._cache.clear()

    def __del__(self):
        self.pool.shutdown()

if __name__ == '__main__':
    args = parser.parse_args()
    logging.basicConfig(level=args.level, format='%(asctime)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)s:%(message)s')
    logging.info(json.dumps(vars(args)))
    logging.info('running apis are {}'.format(req.url_handlers))
    try:
        cache = redis.Redis(db=1)
        cache.scan()
    except redis.ConnectionError:
        cache = SimpleCache()
        def exists(key):
            return key in cache._cache
        cache.exists = exists
    server = MainServer(args, cache)
    server.start_cron()
    logging.info('running cron jobs are {}'.format(req.cron.keys()))
    autoreload.add_reload_hook(server.__del__)
    loop = ioloop.IOLoop.instance().start()
