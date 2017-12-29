#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
# import link
import os

from util import genUUID, objToDictionnary

class Process(metaclass=ABCMeta):
    def __init__(self, data={}):
        # self.filepath = filepath
        self.uuid = genUUID()
        self._pid = os.getpid()
        # self.name = name if name is not None else os.path.basename(filepath)
        # self.link_manager = link.Link_manager(uuid)

        self.name = data.get('name', self.uuid)
        self.type = data.get('type', None)
        self.description = data.get('description', '')
        self.bulletin_level = data.get('bulletin_level', 'WARNING')
        self.x = data.get('x', 0)
        self.y = data.get('y', 0)

    def change_name(self, name):
        self.name = name

    def get_representation(self):
        return objToDictionnary(self)

    # def run(self):
    #     for msg in self.link_manager.get_message():
    #         if msg is not None:
    #             self.process_message(msg)
    #         else:
    #             sleep(self.config.process.sleepTime)
    #
    # def push_message(self, msg):
    #         self.link_manager.push_message(msg)

    @abstractmethod
    def process_message(self, msg):
        pass
