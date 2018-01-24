#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

class Multiplexer_out(Process):
    def process_message(self, msg, **kargs):
        self.custom_message = 'Multiplexer logic: {}'.format(self.custom_config['multiplex_logic'])
        self.forward(msg, pipeline=True,**kargs)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Multiplexer_out(uuid)
