#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

class File_reader(Process):
    def process_message(self, msg, channel):
        try:
            with open(msg, 'r') as f:
                content = f.read()
            self.custom_message = 'last file-path received: '+msg
            self.forward(content)
        except IOError as e:
            self.custom_message = str(e)

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = File_reader(uuid)
