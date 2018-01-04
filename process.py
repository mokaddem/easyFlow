#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
# import link
import os, time, sys
import redis, json

from util import genUUID, objToDictionnary
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface

host='localhost'
port=6780
db=0

class Process(metaclass=ABCMeta):
    def __init__(self, puuid):
        # get config from redis
        self._serv_config = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self._alert_manager = Alert_manager()
        self.puuid = puuid
        self.pid = os.getpid()
        configData = self._serv_config.get('config_'+puuid)
        configData = json.loads(configData)
        self._serv_config.delete('config_'+puuid)

        # self.filepath = filepath
        self._keyCommands = 'keyCommands'
        # self.name = name if name is not None else os.path.basename(filepath)
        # self.link_manager = link.Link_manager(uuid)

        self.projectUUID = configData.get('projectUUID', 'No projectUUID')
        self.name = configData.get('name', 'No name')
        self.type = configData.get('type', None)
        self.description = configData.get('description', '')
        self.bulletin_level = configData.get('bulletin_level', 'WARNING')
        self.x = configData.get('x', 0)
        self.y = configData.get('y', 0)
        self.connections = []

        self._metadata_interface = Process_metadata_interface()
        self._alert_manager = Alert_manager()
        self.push_p_info()
        print('process {} [{}] ready'.format(self.puuid, self.pid))
        self.run()


    def change_name(self, name):
        self.name = name

    def get_uuid(self):
        return self.puuid

    def get_representation(self, full=False):
        return objToDictionnary(self, full=full)

    def push_p_info(self):
        self.timestamp = time.time()
        self._metadata_interface.push_info(self.get_representation())

    def push_process_start(self):
        self._alert_manager.send_alert(
            title=self.name,
            content='{state}[{pid}] ({now})'.format(
                now=time.strftime('%H:%M:%S'),
                pid=self.pid,
                state="started"
            ),
            mType='info',
            group=self.projectUUID+'_processes'
        )

    '''
        - Process incoming commands
        - Push self info
        - Process messages
    '''
    def run(self):
        self.push_process_start()
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
            print('process {} [{}]: sleeping'.format(self.puuid, self.pid))


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
