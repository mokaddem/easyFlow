#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(curdir, '..'))

import time
import signal
from abc import ABCMeta, abstractmethod
from process import Process
from link_manager import FlowItem


class Process_no_input(Process, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        signal.signal(signal.SIGUSR1, self.sig_handler)
        super().__init__(*args, **kwargs)

    def sig_handler(self, signum, frame):
        self.process_commands()

    def process_message(self, msg):
        pass

    @abstractmethod
    def generate_data(self):
        pass

    def run(self):
        self.push_process_start()
        while True:
            # No commands in generators modules
            self.push_p_info()
            self.generate_data()

            time.sleep(0.1)
            # print('process {} [{}]: sleeping'.format(self.puuid, self.pid))

    # forward is called from generate_data().
    def forward(self, msg):
        self.push_p_info()
        flowItem = FlowItem(msg)
        self._processStat.register_forward(flowItem)
        self._link_manager.push_flowItem(flowItem)
