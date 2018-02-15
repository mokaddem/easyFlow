#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from {procExtendTypeClass} import {procExtendType}

# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: {parameters}


class {processType}({procExtendType}):

    def process_message(self, msg, **kargs):
        self.forward(msg, **kargs)


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = {processType}(uuid)
