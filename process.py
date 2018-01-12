#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
import os, time, sys
import psutil
import redis, json

from util import genUUID, objToDictionnary, SummedTimeSpanningArray, Config_parser
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface, Buffer_metadata_interface
from link_manager import Link_manager, Multiple_link_manager, FlowItem

class Process(metaclass=ABCMeta):
    def __init__(self, puuid):
        self.config = Config_parser('config/easyFlow_conf.json').get_config()
        try:
            self._serv_config = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._serv_config = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)

        self._alert_manager = Alert_manager()
        self.puuid = puuid
        self.pid = os.getpid()
        self._p = psutil.Process()
        self.custom_message = ""
        self._keyCommands = 'command_'+self.puuid
        self.state = 'running'

        self.update_config()

        self._metadata_interface = Process_metadata_interface()
        self._buffer_metadata_interface = Buffer_metadata_interface()
        self.last_refresh = time.time() - self.state_refresh_rate # ensure a refresh

        self._processStat = ProcessStat(self.config.default_project.process.buffer_time_spanned_in_min)
        self.push_p_info()

        if self.type == 'multiplexer_in':
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, multi_in=True)
        elif self.type == 'multiplexer_out':
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, multi_in=False)
        else:
            self._link_manager = Link_manager(self.projectUUID, self.puuid, self.custom_config)

        self.run()

    def update_config(self):
        configData = self._serv_config.get('config_'+self.puuid)
        if configData is None: # already updated. Should not happend
            return
        configData = json.loads(configData)
        self.custom_config = configData['custom_config']
        self._serv_config.delete('config_'+self.puuid)

        self.state_refresh_rate = self.config.web.refresh_metadata_interval_in_sec

        self.projectUUID = configData.get('projectUUID', 'No projectUUID')
        self.name = configData.get('name', 'No name')
        self.type = configData.get('type', None)
        self.description = configData.get('description', '')
        self.bulletin_level = configData.get('bulletin_level', 'WARNING')
        self.x = configData.get('x', 0)
        self.y = configData.get('y', 0)
        self.config = Config_parser('config/easyFlow_conf.json', self.projectUUID).get_config()

    def reload(self):
        self.update_config()
        self._link_manager.update_connections(self.custom_config)

    def change_name(self, name):
        self.name = name

    def get_uuid(self):
        return self.puuid

    def get_system_info(self):
        to_ret = {}
        to_ret['cpu_load'] = self._p.cpu_percent()
        to_ret['memory_load'] = self._p.memory_info().rss
        to_ret['pid'] = self.pid
        to_ret['state'] = self.state
        to_ret['custom_message'] = self.custom_message
        return to_ret

    def get_representation(self, full=False):
        pInfo = objToDictionnary(self, full=full)
        dStat = self._processStat.get_dico()
        dStat.update(self.get_system_info())
        pInfo['stats'] = dStat
        return pInfo

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

            if self.state == 'running':
                # Process flowItems
                flowItem = self._link_manager.get_flowItem()
                if flowItem is not None: # if not part of the flow yet
                    self._processStat.register_processing(flowItem)
                    self.process_message(flowItem.message())
                    self._processStat.register_processed()
                else:
                    time.sleep(self.config.default_project.process.pooling_time_interval_get_message)

            else: # process paused
                time.sleep(self.config.default_project.process.pooling_time_interval_get_message)


    def forward(self, msg):
        flowItem = FlowItem(msg)
        if self._link_manager.push_flowItem(flowItem):
            self._processStat.register_forward(flowItem)

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
        elif operation == 'play':
            self.play()
        else:
            pass

    def pause(self):
        self.state = 'paused'

    def play(self):
        self.state = 'running'

    @abstractmethod
    def process_message(self, msg):
        pass

class ProcessStat:
    def __init__(self, buffer_time_spanned_in_min):
        self._start_processing_time = 0
        self.timeSpannedByArray = buffer_time_spanned_in_min*60 # seconds
        self.processing_time = 0
        self._bytes_in = SummedTimeSpanningArray(self.timeSpannedByArray)
        self._bytes_out = SummedTimeSpanningArray(self.timeSpannedByArray)
        self._flowItem_in = SummedTimeSpanningArray(self.timeSpannedByArray)
        self._flowItem_out = SummedTimeSpanningArray(self.timeSpannedByArray)

    def register_processing(self, flowItem):
        self._start_processing_time = time.time()
        self._bytes_in.add(flowItem.size)
        self._flowItem_in.add(1)

    def register_processed(self):
        self._start_processing_time = 0

    def compute_processing_time(self):
        if self._start_processing_time == 0: # currently not processing
            self.processing_time = 0
        else:
            self.processing_time = time.time() - self._start_processing_time

    def register_forward(self, flowItem):
        self._bytes_out.add(flowItem.size)
        self._flowItem_out.add(1)


    def __repr__(self):
        return json.dumps(self.get_dico())

    def get_dico(self):
        self.compute_processing_time();
        to_ret = objToDictionnary(self)

        to_ret['bytes_in'] = self._bytes_in.get_sum()
        to_ret['bytes_out'] = self._bytes_out.get_sum()
        to_ret['flowItem_in'] = self._flowItem_in.get_sum()
        to_ret['flowItem_out'] = self._flowItem_out.get_sum()
        return to_ret

    def __str__(self):
        return self.__repr__()
