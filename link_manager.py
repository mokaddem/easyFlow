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

class Link_manager:
    def __init__(self, projectUUID, puuid):
        # from puuid, get buuid
        self.projectUUID = projectUUID
        self.puuid = puuid
        self._serv = redis.Redis(unix_socket_path='/tmp/redis.sock', decode_responses=True)
        # ONLY 1 ingress and 1 egress
        self.ingress = None
        self.egress = None
        self.update_connections()
        self.partOfTheFlow = False

    def update_connections(self):
        self.ingress = None
        self.egress = None
        config = self.get_config()

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
            flowItem = self._serv.rpop(self.ingress)
            return flowItem
        else:
            # Either return None or wait until part of the flow
            return None

    def push_flowItem(self, flowItem):
        if self.egress is not None:
            self._serv.lpush(self.egress, flowItem)

    def get_config(self):
        return json.loads(self._serv.get(self.projectUUID))['buffers']

    def show_connections(self):
        print('{} -> {} -> {}'.format(self.ingress, self.puuid, self.egress))



class Multiple_link_manager(Link_manager):
    def __init__(self, projectUUID, puuid, custom_config, multi_in=True):
        super().__init__(projectUUID, puuid)
        self.custom_config = custom_config
        self.multi_in = multi_in
        self.multi_out = not multi_in
        self.ingress = []
        self.egress = []
        print('MULTIPLE LINK MANAGER FOR '+puuid)

        self.update_connections()
        self.mult_logic = self.custom_config['multiplex_logic']
        self.interleave_index = 0 # last poped buffer index

    def inc_interleave_index(self):
        if self.multi_in:
            self.interleave_index = self.interleave_index+1 if self.interleave_index < len(self.ingress)-1 else 0
        else:
            self.interleave_index = self.interleave_index+1 if self.interleave_index < len(self.egress)-1 else 0

    def update_connections(self):
        self.ingress = []
        self.egress = []
        config = self.get_config()

        for buuid, bConfig in config.items():
            procTo = bConfig['toUUID']
            procFrom = bConfig['fromUUID']
            if procTo == self.puuid:
                self.ingress.append(buuid)
            if procFrom == self.puuid:
                self.egress.append(buuid)

    def get_flowItem(self):
        if self.multi_in: # custom logic: interleaving, priority
            if self.mult_logic == 'Interleave':
                # print('popping from '+self.ingress[self.interleave_index])
                flowItem = self._serv.rpop(self.ingress[self.interleave_index])
                self.inc_interleave_index()
            elif self.mult_logic == 'Priority':
                print('ingoring priority for the moment')
                flowItem = self._serv.rpop(self.ingress[self.interleave_index])
                self.inc_interleave_index()
            else:
                print('Unkown multiplexer logic')
            return flowItem

        else: # same as simple link manager
            flowItem = self._serv.rpop(self.ingress[0])
            return flowItem

    def push_flowItem(self, flowItem):
        if self.multi_out: # custom logic: copy, dispatch
            if self.mult_logic == 'Interleave':
                self._serv.lpush(self.egress[self.interleave_index], flowItem)
                self.inc_interleave_index()
            elif self.mult_logic == 'Priority':
                print('ingoring priority for the moment')
                self._serv.lpush(self.egress[self.interleave_index], flowItem)
                self.inc_interleave_index()
            else:
                print('Unkown multiplexer logic')
        else: # same as simple link manager
            self._serv.lpush(self.egress[0], flowItem)
