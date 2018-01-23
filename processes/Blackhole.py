#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: dict_keys([])


class Blackhole(Process):

    def process_message(self, msg, channel):
        pass


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Blackhole(uuid)
