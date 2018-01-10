#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(curdir, '..'))

from process import Process

class Print_to_console(Process):
    def process_message(self, msg):
        print('Print_to_console [{}]: {}'.format(os.getpid(), msg))
        # self.forward(msg)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Print_to_console(uuid)
