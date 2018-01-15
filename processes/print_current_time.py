#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys
sys.path.append('..')
from process import Process
import time

class Print_to_console(Process):
    def process_message(self, msg, channel):
        print(time.time())

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Print_to_console(uuid)
