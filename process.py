#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
# import link
import os, time, sys
import redis, json

from util import genUUID, objToDictionnary
from process_metadata_interface import Process_metadata_interface

host='localhost'
port=6780
db=0

class Process(metaclass=ABCMeta):
    def __init__(self, uuid):
        # get config from redis
        self._serv_config = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self.uuid = uuid
        self.pid = os.getpid()
        configData = self._serv_config.get('config_'+uuid)
        configData = json.loads(configData)
        self._serv_config.delete('config_'+uuid)

        # self.filepath = filepath
        self._keyCommands = 'keyCommands'
        # self.name = name if name is not None else os.path.basename(filepath)
        # self.link_manager = link.Link_manager(uuid)

        self.name = configData.get('name', self.uuid)
        self.type = configData.get('type', None)
        self.description = configData.get('description', '')
        self.bulletin_level = configData.get('bulletin_level', 'WARNING')
        self.x = configData.get('x', 0)
        self.y = configData.get('y', 0)

        self._metadata_interface = Process_metadata_interface()
        self.push_p_info()
        print('process {} [{}] ready'.format(self.uuid, self.pid))
        self.run()


    def change_name(self, name):
        self.name = name

    def get_uuid(self):
        return self.uuid

    def get_representation(self, full=False):
        return objToDictionnary(self, full=full)

    def push_p_info(self):
        self.timestamp = time.time()
        self._metadata_interface.push_info(self.get_representation())

    '''
        - Process incoming commands
        - Push self info
        - Process messages
    '''
    def run(self):
        while True:
            flag_cmds = True

            # Process incoming commands
            while flag_cmds:
                # jCommand = self.serv.rpop(self.keyCommands)
                jCommand = None
                if jCommand: # there is a message
                    applyOperation(jCommand['operation'], jCommand['data'])
                else:
                    flag_cmds = False

            self.push_p_info()


            time.sleep(1)
            print('process {} [{}]: sleeping'.format(self.uuid, self.pid))


    # def push_message(self, msg):
    #         self.link_manager.push_message(msg)





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
