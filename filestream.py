#!/usr/bin/env python
import os
import time
import logging
import argparse
from collections import defaultdict

CURDIR = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--path', default=CURDIR, help='directory for file read')
parser.add_argument('-s', '--sleep', default=0.1, type=int, help='sleep timeer')
parser.add_argument('-f', '--filename', required=True, help='tailing filename')

class FileStreamer(object):
    filehandle = {}
    listener = defaultdict(lambda :0)
    def __init__(self, path, callback=logging.info, sleep=1, seek=0, logger=logging.getLogger('root')):
        self.path = path
        self.logger = logger
        self.callback = callback
        self.sleep = sleep
        self.seek = -abs(seek)

    def tail(self, filename):
        fh = open(filename)
        try:
            fh.seek(self.seek, 2)
        except IOError:
            fh.seek(0, 2)
        while True:
            line = fh.readline()
            if not line:
                yield None
            else:
                yield line

    def subscribe(self, filename):
        fullpath = os.path.join(self.path, filename)
        if '..' in fullpath:
            self.logger.warn('naughty filename with ..')
            return
        if os.path.isfile(fullpath):
            self.filehandle[filename] = self.tail(fullpath)
            self.listener[filename] += 1
        else:
            self.logger.error('file {} does not exist'.format(filename))

    def unsubscribe(self, filename):
        if filename in self.filehandle:
            del self.filehandle[filename]
            self.listener[filename] -= min(self.listener[filename], 1)

    def listen(self):
        for filename, count in self.listener.items():
            if count > 0:
                line = next(self.filehandle[filename])
                if line is not None:
                    if not isinstance(line, str):
                        line = str(line)
                    self.callback({filename:line})
                    yield {filename: line}
                else:
                    yield None
            else:
                del self.listener[filename]

    def run(self):
        while True:
            for line in self.listen():
                continue
            time.sleep(self.sleep)
        
if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    args = parser.parse_args()
    stream = FileStreamer(args.path, sleep=args.sleep)
    stream.subscribe(args.filename)
    stream.run()
