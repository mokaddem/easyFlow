#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

class Print_to_console(Process):
    def process_message(self, msg, channel):
        print('Print_to_console [{}]: {}'.format(os.getpid(), msg))
        self.logger.debug('Printed: %s', msg)
        self.custom_message = 'last printed: '+msg[0:20]
        # self.forward(msg)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Print_to_console(uuid)
