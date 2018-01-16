#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

class Multiplexer_in(Process):
    def process_message(self, msg, channel):
        self.custom_message = 'Multiplexer logic: {}'.format(self.custom_config['multiplex_logic'])
        self.forward(msg)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Multiplexer_in(uuid)
