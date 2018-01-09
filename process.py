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
from link_manager import Link_manager, Multiple_link_manager

host='localhost'
port=6780
db=0

class Process(metaclass=ABCMeta):
    def __init__(self, puuid):
        # get config from redis
        # self._serv_config = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self._serv_config = redis.Redis(unix_socket_path='/tmp/redis.sock', decode_responses=True)
        self._alert_manager = Alert_manager()
        self.puuid = puuid
        self.pid = os.getpid()
        self._keyCommands = 'command_'+self.puuid

        self.update_config()

        self._metadata_interface = Process_metadata_interface()
        self.last_refresh = time.time() - self.state_refresh_rate # ensure a refresh
        self.push_p_info()

        if self.type == 'multiplexer_in':
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, multi_in=True)
        elif self.type == 'multiplexer_out':
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, multi_in=False)
        else:
            self._link_manager = Link_manager(self.projectUUID, self.puuid)

        self.run()

    def update_config(self):
        configData = self._serv_config.get('config_'+self.puuid)
        if configData is None: # already updated. Should not happend
            return
        configData = json.loads(configData)
        self.custom_config = configData['custom_config']
        self._serv_config.delete('config_'+self.puuid)

        self.state_refresh_rate = 1

        self.projectUUID = configData.get('projectUUID', 'No projectUUID')
        self.name = configData.get('name', 'No name')
        self.type = configData.get('type', None)
        self.description = configData.get('description', '')
        self.bulletin_level = configData.get('bulletin_level', 'WARNING')
        self.x = configData.get('x', 0)
        self.y = configData.get('y', 0)

    def reload(self):
        self.update_config()
        self._link_manager.update_connections()

    def change_name(self, name):
        self.name = name

    def get_uuid(self):
        return self.puuid

    def get_representation(self, full=False):
        return objToDictionnary(self, full=full)

    # push current process info to redis depending on the refresh value.
    def push_p_info(self):
        now = time.time()
        if now - self.last_refresh > self.state_refresh_rate:
            self.timestamp = now
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

    def process_commands(self):
        while True:
            rawCommand = self._serv_config.rpop(self._keyCommands)
            if rawCommand is not None: # there is a message
                jCommand = json.loads(rawCommand)
                self.apply_operation(jCommand['operation'], jCommand.get('data', None))
            else:
                break

    '''
        - Process incoming commands
        - Push self info
        - Process messages
    '''
    def run(self):
        self.push_process_start()
        while True:

            # Process incoming commands
            self.process_commands()

            # send info about current module state
            self.push_p_info()

            # Process flowItems
            flowItem = self._link_manager.get_flowItem()
            if flowItem is not None: # if not part of the flow yet
                # msg = flowItem['message']
                self.process_message(flowItem)
            else:
                time.sleep(0.5)
            # print('process {} [{}]: sleeping'.format(self.puuid, self.pid))


    def forward(self, msg):
        self._link_manager.push_flowItem(msg)

    def apply_operation(self, operation, data):
        if operation == 'reload':
            self.reload()
            self._alert_manager.send_alert(
                title=self.name,
                content='got reloaded ({now})'.format(
                    now=time.strftime('%H:%M:%S')
                ),
                mType='info'
            )
        elif operation == 'pause':
            self.pause()
        elif operation == 'start':
            self.start()
        else:
            pass

    def pause(self):
        pass

    def start(self):
        pass

    @abstractmethod
    def process_message(self, msg):
        pass
