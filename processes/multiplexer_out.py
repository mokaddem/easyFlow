#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(curdir, '..'))

from process import Process

class Multiplexer_out(Process):
    def process_message(self, msg, channel):
        self.custom_message = 'Multiplexer logic: {}'.format(self.custom_config['multiplex_logic'])
        self.forward(msg)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Multiplexer_out(uuid)
