#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(curdir, '..'))

from process import Process

class Switch(Process):
    def process_message(self, msg, channel, **kargs):
        self.forward(msg, channel=channel, **kargs)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Switch(uuid)
