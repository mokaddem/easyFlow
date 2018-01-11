#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
# import link
import os, time, sys
import redis, json

from util import genUUID, objToDictionnary
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface, Buffer_metadata_interface

class Link_manager:
    def __init__(self, projectUUID, puuid, custom_config):
        # from puuid, get buuid
        self.projectUUID = projectUUID
        self.puuid = puuid
        self._serv = redis.Redis(unix_socket_path='/tmp/redis.sock', decode_responses=True)
        self.custom_config = custom_config
        # ONLY 1 ingress and 1 egress
        self.ingress = None
        self.egress = None
        self.update_connections(custom_config)
        self.partOfTheFlow = False

        self._buffer_metadata_interface = Buffer_metadata_interface()

    def update_connections(self, custom_config):
        self.ingress = None
        self.egress = None
        config = self.get_config()

        self.custom_config = custom_config

        for buuid, bConfig in config.items():
            procTo = bConfig['toUUID']
            procFrom = bConfig['fromUUID']
            if procTo == self.puuid:
                self.ingress = buuid
            if procFrom == self.puuid:
                self.egress = buuid
        # self.show_connections()

    def get_flowItem(self):
        if self.ingress is not None:
            flowItem_raw = self._serv.rpop(self.ingress)
            if flowItem_raw is None:
                return None
            else:
                flowItem = FlowItem(flowItem_raw, raw=True)
                self._buffer_metadata_interface.push_info(self.ingress, -flowItem.size) # decrease buffer size
                return flowItem
        else:
            # Either return None or wait until part of the flow
            return None

    def push_flowItem(self, flowItem):
        if self.egress is not None:
            self._buffer_metadata_interface.push_info(self.egress, flowItem.size) # increase buffer size
            self._serv.lpush(self.egress, flowItem)

    def get_config(self):
        return json.loads(self._serv.get(self.projectUUID))['buffers']

    def show_connections(self):
        print('{} -> {} -> {}'.format(self.ingress, self.puuid, self.egress))



class Multiple_link_manager(Link_manager):
    def __init__(self, projectUUID, puuid, custom_config, multi_in=True):
        super().__init__(projectUUID, puuid, custom_config)
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
        self.ingress = []
        self.egress = []
        config = self.get_config()

        self.custom_config = custom_config

        for buuid, bConfig in config.items():
            procTo = bConfig['toUUID']
            procFrom = bConfig['fromUUID']
            if procTo == self.puuid:
                self.ingress.append(buuid)
            if procFrom == self.puuid:
                self.egress.append(buuid)

    def get_flowItem(self):
        if len(self.ingress) > 0: # check that has at least 1 ingess connection
            if self.multi_in: # custom logic: interleaving, priority
                if self.custom_config['multiplex_logic'] == 'Interleave':
                    # print('popping from '+self.ingress[self.interleave_index])
                    flowItem_raw = self._serv.rpop(self.ingress[self.interleave_index])
                    self.inc_interleave_index()
                elif self.custom_config['multiplex_logic'] == 'Priority':
                    print('ingoring priority for the moment')
                    flowItem_raw = self._serv.rpop(self.ingress[self.interleave_index])
                    self.inc_interleave_index()
                else:
                    print('Unkown multiplexer logic')

                if flowItem_raw is None:
                    return None
                else:
                    flowItem = FlowItem(flowItem_raw, raw=True)
                    self._buffer_metadata_interface.push_info(self.ingress[self.interleave_index], -flowItem.size) # decrease buffer size
                    return flowItem

            else: # same as simple link manager
                flowItem_raw = self._serv.rpop(self.ingress[0])
                if flowItem_raw is None:
                    return None
                else:
                    flowItem = FlowItem(flowItem_raw, raw=True)
                    self._buffer_metadata_interface.push_info(self.ingress[0], -flowItem.size) # decrease buffer size
                    return flowItem

    def push_flowItem(self, flowItem):
        if len(self.egress) > 0: # check that has at least 1 egress connection
            if self.multi_out: # custom logic: copy, dispatch
                if self.custom_config['multiplex_logic'] == 'Interleave':
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index], flowItem.size) # increase buffer size
                    self._serv.lpush(self.egress[self.interleave_index], flowItem)
                    self.inc_interleave_index()
                elif self.custom_config['multiplex_logic'] == 'Priority':
                    print('igoring priority for the moment')
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index], flowItem.size) # increase buffer size
                    self._serv.lpush(self.egress[self.interleave_index], flowItem)
                    self.inc_interleave_index()
                elif self.custom_config['multiplex_logic'] == 'Duplicate':
                    for key in self.egress:
                        self._buffer_metadata_interface.push_info(key, flowItem.size) # increase buffer size
                        self._serv.lpush(key, flowItem)
                else:
                    print('Unkown multiplexer logic')
            else: # same as simple link manager
                self._buffer_metadata_interface.push_info(self.egress[0], flowItem.size) # increase buffer size
                self._serv.lpush(self.egress[0], flowItem)

class FlowItem:
    def __init__(self, content, origin=None, raw=False):
        if raw:
            if content is None:
                self.content = None
            else:
                jflowItem = json.loads(content)
                self.content = jflowItem['content']
                self.size = jflowItem['size']
                self.origin = jflowItem['origin']
        else:
            self.content = content
            self.size = len(content.encode('utf-8'))
            self.origin = origin

    def message(self):
        return self.content

    def __repr__(self):
        return json.dumps(objToDictionnary(self))

    def __str__(self):
        return self.__repr__()
