#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

import time
import signal

from abc import ABCMeta, abstractmethod
from util import Config_parser
from process import Process
from link_manager import FlowItem

class Process_no_input(Process, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        signal.signal(signal.SIGUSR1, self.sig_handler)
        super().__init__(*args, **kwargs)

    def sig_handler(self, signum, frame):
        self.logger.debug('Signal received')
        self.process_commands()
        self.push_p_info()

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
            if self.state == 'running':
                self._processStat.register_processing(FlowItem(""))
                self.generate_data()
                self._processStat.register_processed()
                time.sleep(self.config.default_project.process.pooling_time_interval_get_message)
            else: # process paused
                self.logger.debug('Process state: %s, sleeping %s sec', self.state, self.config.default_project.process.pooling_time_interval_get_message)
                time.sleep(self.config.default_project.process.pooling_time_interval_get_message)

    # forward is called from generate_data().
    def forward(self, msg, pipeline=False, channel=0, redirect=False):
        self.push_p_info()
        flowItem = FlowItem(msg, channel=channel, redirect=redirect)
        if self._link_manager.push_flowItem(flowItem, pipeline=pipeline):
            self._processStat.register_forward(flowItem)
