import sys
import logging
import json
from filestream import FileStreamer

logger = logging.getLogger(__name__)

class Registry(dict):
    def register(self, fn):
        self['{}'.format(fn.__name__)] = fn
        return fn

api_registry = Registry()
def debug_log(msg):
    logger.debug(json.dumps(msg))

# File Streamer API
stream = FileStreamer(path='.', callback=debug_log, sleep=0, seek=0)
@api_registry.register
def subscribe_log(filename, **kwargs):
    if isinstance(filename, (list, tuple)):
        filename = filename[0]
    if not filename.endswith('.log'):
        stream.logger.warn('not a log file')
        return
    stream.subscribe(filename)

@api_registry.register
def unsubscribe_log(filename, **kwargs):
    if isinstance(filename, (list, tuple)):
        filename = filename[0]
    stream.unsubscribe(filename)

@api_registry.register
def stream_listen():
    return stream.listen()
