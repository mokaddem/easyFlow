#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
import os, time, sys
import redis, json

from util import genUUID, objToDictionnary, Config_parser
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface, Buffer_metadata_interface
easyFlow_conf = os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')

class Link_manager:
    def __init__(self, projectUUID, puuid, custom_config, logger):
        self.logger = logger

        self.config = Config_parser(easyFlow_conf, projectUUID).get_config()
        # from puuid, get buuid
        self.projectUUID = projectUUID
        self.puuid = puuid
        try:
            self._serv_config = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._serv_config = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)

        try:
            self._serv_buffers = redis.Redis(unix_socket_path=self.config.redis.buffers.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._serv_buffers = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)


        self.custom_config = custom_config
        # ONLY 1 ingress and 1 egress
        self.ingress = None
        self.egress = None
        self.update_connections(custom_config)
        self.partOfTheFlow = False

        self._buffer_metadata_interface = Buffer_metadata_interface()

    def update_connections(self, custom_config):
        self.logger.debug('updating connections')
        self.ingress = None
        self.egress = None
        config = self.get_config()

        self.custom_config = custom_config

        for buuid, bConfig in config.items():
            procTo = bConfig['toUUID']
            procFrom = bConfig['fromUUID']
            if procTo == self.puuid:
                self.ingress = buuid
                self.bufType = bConfig.get('type', None)
            if procFrom == self.puuid:
                self.egress = buuid
        # self.show_connections()

    def buffer_pop(self, target):
        if self.bufType == 'FIFO':
            flowItem_raw = self._serv_buffers.rpop(target)
        elif self.bufType == 'LIFO':
            flowItem_raw = self._serv_buffers.lpop(target)
        else:
            flowItem_raw = None
        return flowItem_raw

    def get_flowItem(self):
        if self.ingress is not None:
            flowItem_raw = self.buffer_pop(self.ingress)

            if flowItem_raw is None:
                return None
            else:
                flowItem = FlowItem(flowItem_raw, raw=True)
                self._buffer_metadata_interface.push_info(self.ingress, -flowItem.size) # decrease buffer size
                return flowItem
        else:
            # Either return None or wait until part of the flow
            self.logger.warning('Process wanted to get message but no ingress connection is registered')
            return None

    def push_flowItem(self, flowItem):
        if self.egress is not None:
            self._buffer_metadata_interface.push_info(self.egress, flowItem.size) # increase buffer size
            self._serv_buffers.lpush(self.egress, flowItem)
            return True
        else:
            self.logger.warning('Process wanted to push message but no egress connection is registered')
            return False

    def get_config(self):
        return json.loads(self._serv_config.get(self.projectUUID))['buffers']

    def show_connections(self):
        print('{} -> {} -> {}'.format(self.ingress, self.puuid, self.egress))


class Multiple_link_manager(Link_manager):
    def __init__(self, projectUUID, puuid, custom_config, logger, multi_in=True, is_switch=False):
        self.logger = logger
        self.is_switch = is_switch
        super().__init__(projectUUID, puuid, custom_config, logger)
        self.custom_config = custom_config
        self.multi_in = multi_in
        self.multi_out = not multi_in
        self.ingress = []
        self.egress = []

        self.update_connections(custom_config)
        self.interleave_index = 0 # last poped buffer index

    def inc_interleave_index(self):
        if self.multi_in:
            self.interleave_index = self.interleave_index+1 if self.interleave_index < len(self.ingress)-1 else 0
        else:
            self.interleave_index = self.interleave_index+1 if self.interleave_index < len(self.egress)-1 else 0

    def update_connections(self, custom_config):
        self.logger.debug('updating connections')
        self.custom_config = custom_config
        config = self.get_config()
        self.ingress = []
        self.egress = []

        for buuid, bConfig in config.items():
            procTo = bConfig['toUUID']
            procFrom = bConfig['fromUUID']
            if procTo == self.puuid:
                self.ingress.append(buuid)
                self.bufType = bConfig.get('type', None)
            if procFrom == self.puuid:
                self.egress.append(buuid)

        if self.is_switch: # custom_config contains buffer mapping {buuid: channel, ...}
            self.egress = {0: []}
            for buuid, channel in self.custom_config.items():
                if channel not in self.egress:
                    self.egress[channel] = []
                self.egress[channel].append(buuid)
                self.egress[0].append(buuid)


    def get_flowItem(self):
        if len(self.ingress) > 0: # check that has at least 1 ingess connection
            multiplex_logic = self.custom_config.get('multiplex_logic', 'Interleave')
            if self.multi_in: # custom logic: interleaving, priority
                if multiplex_logic == 'Interleave':
                    flowItem_raw = self.buffer_pop(self.ingress[self.interleave_index])
                elif multiplex_logic == 'Priority':
                    self.logger.warning('Ignoring priority for the moment, falling back to "Interleave" multiplex_logic')
                    flowItem_raw = self.buffer_pop(self.ingress[self.interleave_index])
                else:
                    self.logger.warning('Unkown multiplexer logic')

                if flowItem_raw is None:
                    return None
                else:
                    flowItem = FlowItem(flowItem_raw, raw=True)
                    self._buffer_metadata_interface.push_info(self.ingress[self.interleave_index], -flowItem.size) # decrease buffer size
                    self.inc_interleave_index()
                    return flowItem

            else: # same as simple link manager
                flowItem_raw = self.buffer_pop(self.ingress[0])
                if flowItem_raw is None:
                    return None
                else:
                    flowItem = FlowItem(flowItem_raw, raw=True)
                    self._buffer_metadata_interface.push_info(self.ingress[0], -flowItem.size) # decrease buffer size
                    return flowItem
        else:
            self.logger.warning('Process wanted to get message but no ingress connection(s) are registered')

    def push_flowItem(self, flowItem):
        if len(self.egress) > 0: # check that has at least 1 egress connection
            multiplex_logic = self.custom_config.get('multiplex_logic', 'Interleave')
            multiplex_logic = 'Switch' if self.is_switch else multiplex_logic # change multiplex_logic in case of switch
            if self.multi_out: # custom logic: copy, dispatch
                if multiplex_logic == 'Interleave':
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index], flowItem.size) # increase buffer size
                    self._serv_buffers.lpush(self.egress[self.interleave_index], flowItem)
                    self.inc_interleave_index()
                elif multiplex_logic == 'Priority':
                    self.logger.warning('Ignoring priority for the moment, falling back to "Interleave" multiplex_logic')
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index], flowItem.size) # increase buffer size
                    self._serv_buffers.lpush(self.egress[self.interleave_index], flowItem)
                    self.inc_interleave_index()
                elif multiplex_logic == 'Duplicate':
                    for key in self.egress:
                        self._buffer_metadata_interface.push_info(key, flowItem.size) # increase buffer size
                        self._serv_buffers.lpush(key, flowItem)
                elif multiplex_logic == 'Switch':
                    buuids = self.egress.get(flowItem.channel, []) # drop non valid channel
                    for buuid in buuids:
                        self._buffer_metadata_interface.push_info(buuid, flowItem.size) # increase buffer size
                        self._serv_buffers.lpush(buuid, flowItem)
                else:
                    self.logger.warning('Unkown multiplexer logic')
            else: # same as simple link manager
                self._buffer_metadata_interface.push_info(self.egress[0], flowItem.size) # increase buffer size
                self._serv_buffers.lpush(self.egress[0], flowItem)
            return True
        else:
            self.logger.warning('Process wanted to push message but no egress connection(s) are registered')
            return False

class FlowItem:
    def __init__(self, content, origin=None, raw=False, channel=0, is_json=False):
        if raw:
            if content is None:
                self.content = None
            else:
                jflowItem = json.loads(content)
                self.content = jflowItem['content']
                self.size = jflowItem['size']
                self.origin = jflowItem['origin']
                # self.channel = jflowItem['channel'] ## ignore no channel...
                self.channel = jflowItem['channel'] ## ignore no channel...
                # if self.is_json:
                #     self.content = json.loads(self.content)
        else:
            self.content = content
            if isinstance(content, dict):
                # msg = json.dumps(dict)
                self.size = len(json.dumps(self.content).encode('utf-8'))
            else:
                self.size = len(self.content.encode('utf-8'))
            self.origin = origin
            self.channel = channel
            # self.is_json = is_json

    def message(self):
        return self.content

    def __repr__(self):
        return json.dumps(objToDictionnary(self))

    def __str__(self):
        return self.__repr__()
