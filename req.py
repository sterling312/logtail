import json
import logging
from urllib2 import urlparse
from tornado import web, gen, log, websocket, httputil
from data_server import UrlHandler, BaseHandler, BaseWSHandler, Cron 
import api

url_handlers = UrlHandler()
cron = Cron()

@cron.callback('logstream', 1000*0.1)
@gen.coroutine
def listen_to_log():
    for line in cron.api_call('stream_listen'):
        if line is not None:
            yield LogFeed.broadcast(line)

# Main Handlers
class CachelessStaticHandler(web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header('Cache-Control', 'no-store, no-cache, must-validate, max-age=0'), 

class PartialStaticHandler(web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header('Cache-Control', 'no-store, no-cache, must-validate, max-age=0'), 

    @gen.coroutine
    def get(self, path, include_body=True):
        self.path = self.parse_url_path(path)
        del path
        absolute_path = self.get_absolute_path(self.root, self.path)
        self.absolute_path = self.validate_absolute_path(self.root, absolute_path)
        if self.absolute_path is None:
            return
        self.modified - self.get_modified_time()
        self.set_headers()
        range_header = self.request.headers.get('Range')
        request_range = httputil._parse_request_range(range_header) if range_header else None
        size = self.get_content_size()

@url_handlers.route('/')
class MainHandler(BaseHandler):
    def get(self):
        self.redirect('/api')

@url_handlers.route('/api')
class APIMainHandler(BaseHandler):
    def get(self):
        urls = []
        for path in url_handlers.http:
            url = urlparse.SplitResult(scheme='http', netloc=self.request.host, path=path, query='', fragment='').geturl()
            urls.append(url)
        self.write({'url': urls})

# API Handlers
@url_handlers.api
class LogReader(BaseHandler):
    visible = True
    active = True
    def get(self):
        filename = self.params.get('filename')
        if not filename:
            self.write('set log name as filename')
            return
        ws_url = urlparse.SplitResult(scheme='ws', netloc=self.request.host, path=self.reverse_url('logfeed'), query=self.request.query, fragment='').geturl()
        if isinstance(filename, (list, tuple)):
            filename = filename[0]
        header = self.env.element('script', src='/static/js/ws.js', tostring=True)
        content = self.env.element('div', 
                                   'Listening to {}'.format(filename), 
                                   self.env.element('div', ws_url, id='ws_url', style='display: none'), 
                                   self.env.element('div', class_='stream_object'), 
                                   class_='container', tostring=True)
        self.render_template(title='Live Log', header=header, content=content)

# WebSocket Handlers
@url_handlers.websocket
class LogFeed(BaseWSHandler):
    cl = []
    filename = None
    def open(self):
        filename = self.params.get('filename')
        if isinstance(filename, (list, tuple)):
            filename = filename[0]
        self.filename = filename
        self.logger.info('subscribing to {}'.format(filename))
        self.api_call('subscribe_log', self.filename)
        self.add_client()

    def write_for_subscription(self, msg):
        if isinstance(msg, dict):
            filename, msg = msg.itemss()[0]
        else:
            filename, msg = json.loads(msg).items()[0]
        if filename == self.filename:
            self.write_message(msg)

    def on_close(self):
        self.api_call('unsubscribe_log', self.filename)
        self.remove_client()
