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
        self._serv_config = redis.StrictRedis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)

        self._serv_buffers = redis.StrictRedis(unix_socket_path=self.config.redis.buffers.unix_socket_path, decode_responses=True)
        self._pipeline_buffers = self._serv_buffers.pipeline()
        self.pipeline_counter = 0
        self.pipeline_threshold = 100
        self.pipeline_time_threshold = 1 # sec
        self.pipeline_lastpush = time.time()

        # register redis server for flowItem
        try:
            self.redis_server_redirected_data = redis.Redis(unix_socket_path=self.config.redis.redirected_data.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.error('REDIS SOCKET FOR REDIRECT')
            self.redis_server_redirected_data = redis.StrictRedis(
                self.config.redis.redirected_data.host,
                self.config.redis.redirected_data.port,
                self.config.redis.redirected_data.db,
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

    def buffer_pop(self, target, count=1):
        # fr[0] is key and fr[1] is value
        if self.bufType == 'FIFO':
            # flowItem_raw = self._serv_buffers.brpop(target, 1)
            flowItems_raw = self._serv_buffers.lrange(target, -count, -1)
            self._serv_buffers.ltrim(target, 0, -len(flowItems_raw)-1)
        elif self.bufType == 'LIFO':
            # flowItem_raw = self._serv_buffers.blpop(target, 1)
            flowItems_raw = self._serv_buffers.lrange(target, 0, count)
            self._serv_buffers.ltrim(target, len(flowItems_raw), -1)
        else:
            flowItems_raw = []

        # return flowItem_raw[1] if flowItem_raw is not None else None
        return flowItems_raw

    def get_flowItems(self, count=1):
        if self.ingress is not None:
            flowItems_raw = self.buffer_pop(self.ingress, count=count)
            flowItems_parsed = self.parse_raw_flowItem(flowItems_raw)
            self._buffer_metadata_interface.push_info(self.ingress, flowItems_parsed['summed_size']) # decrease buffer size
            return flowItems_parsed['flowItems']

            # if len(flowItems_raw) == 0:
            #     return []
            # else:
            #     ret = []
            #     for flowItem_raw in flowItems_raw:
            #         flowItem = FlowItem(flowItem_raw, raw=True)
            #         self._buffer_metadata_interface.push_info(self.ingress, -flowItem.size) # decrease buffer size
            #         ret.append(flowItem)
            #     return ret
        else:
            # Either return None or wait until part of the flow
            self.logger.warning('Process wanted to get message but no ingress connection is registered')
            return None

    def push_flowItem(self, flowItem, pipeline=False):
        if self.egress is not None:
            self._buffer_metadata_interface.push_info(self.egress, flowItem.size) # increase buffer size

            if pipeline:
                self.push_flow_pipeline(self.egress, flowItem)
            else:
                self._serv_buffers.lpush(self.egress, flowItem)

            return 1
        else:
            self.logger.warning('Process wanted to push message but no egress connection is registered')
            return 0

    def push_flow_pipeline(self, output, flowItem):
        self._pipeline_buffers.lpush(output, flowItem)
        self.pipeline_counter += 1
        now = time.time()
        if self.pipeline_counter >= self.pipeline_threshold or now-self.pipeline_lastpush >= self.pipeline_time_threshold:
            self._pipeline_buffers.execute()
            self.pipeline_counter = 0
            self.pipeline_lastpush = now

    def parse_raw_flowItem(self, flowItems_raw):
        if len(flowItems_raw) == 0:
            return {'flowItems': [], 'summed_size': 0}
        else:
            ret = []
            summed_size = 0
            for flowItem_raw in flowItems_raw:
                flowItem = FlowItem(flowItem_raw, raw=True)
                summed_size += -flowItem.size
                ret.append(flowItem)
            return {'flowItems': ret, 'summed_size': summed_size}

    def get_config(self):
        return json.loads(self._serv_config.get(self.projectUUID))['buffers']

    def show_connections(self):
        print('{} -> {} -> {}'.format(self.ingress, self.puuid, self.egress))

    def fetch_content(self, msg):
        # message content is the source of the data
        complete_path = msg.split('@') # redis e.g. redis@keyname; fs e.g. fs@/home/user/filename
        source_type =  complete_path[0] # redis, fs (filesystem)
        path = complete_path[1] # path
        if source_type == 'redis':
            ret = self.redis_server_redirected_data.get(path)
            return ret
        elif source_type == 'fs':
            with open(path, 'r') as f:
                return f.read()
        else:
            print('error, not valid source_type')
            return ""


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
        self.interleave_index_push = 0 # last pushed buffer index
        self.interleave_index_get = 0  # last poped buffer index
        self.duplicate_pipeline_counter = 0

    def inc_interleave_index_push(self):
        if self.multi_in:
            self.interleave_index_push = self.interleave_index_push+1 if self.interleave_index_push < len(self.ingress)-1 else 0
        else:
            self.interleave_index_push = self.interleave_index_push+1 if self.interleave_index_push < len(self.egress)-1 else 0

    def inc_interleave_index_get(self):
        if self.multi_in:
            self.interleave_index_get = self.interleave_index_get+1 if self.interleave_index_get < len(self.ingress)-1 else 0
        else:
            self.interleave_index_get = self.interleave_index_get+1 if self.interleave_index_get < len(self.egress)-1 else 0

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

    def get_flowItems(self, count=1):
        if len(self.ingress) > 0: # check that has at least 1 ingress connection
            multiplex_logic = self.custom_config.get('multiplex_logic', 'Interleave')
            if self.multi_in: # custom logic: interleaving, priority
                if multiplex_logic == 'Interleave':
                    flowItems_raw = self.buffer_pop(self.ingress[self.interleave_index_get], count=count)
                elif multiplex_logic == 'Priority':
                    self.logger.warning('Ignoring priority for the moment, falling back to "Interleave" multiplex_logic')
                    flowItems_raw = self.buffer_pop(self.ingress[self.interleave_index_get], count=count)
                else:
                    self.logger.warning('Unkown multiplexer logic')

                flowItems_parsed = self.parse_raw_flowItem(flowItems_raw)
                self._buffer_metadata_interface.push_info(self.ingress[self.interleave_index_get], flowItems_parsed['summed_size']) # decrease buffer size
                self.inc_interleave_index_get()
                return flowItems_parsed['flowItems']
                # if len(flowItems_raw) == 0:
                #     return []
                # else:
                #     ret = []
                #     for flowItem_raw in flowItems_raw:
                #         flowItem = FlowItem(flowItem_raw, raw=True)
                #         self._buffer_metadata_interface.push_info(self.ingress[self.interleave_index_get], -flowItem.size) # decrease buffer size
                #         ret.append(flowItem)
                #     self.inc_interleave_index_get()
                #     return ret

            else: # same as simple link manager
                flowItems_raw = self.buffer_pop(self.ingress[0], count=count)
                flowItems_parsed = self.parse_raw_flowItem(flowItems_raw)
                self._buffer_metadata_interface.push_info(self.ingress[0], flowItems_parsed['summed_size']) # decrease buffer size
                return flowItems_parsed['flowItems']
                # if len(flowItems_raw) == 0:
                #     return []
                # else:
                #     ret = []
                #     for flowItem_raw in flowItems_raw:
                #         flowItem = FlowItem(flowItem_raw, raw=True)
                #         self._buffer_metadata_interface.push_info(self.ingress[0], -flowItem.size) # decrease buffer size
                #         ret.append(flowItem)
                #     return ret
        else:
            self.logger.warning('Process wanted to get message but no ingress connection(s) are registered')

    def push_flowItem(self, flowItem, pipeline=False):
        if len(self.egress) > 0: # check that has at least 1 egress connection
            pushed_count = 1
            multiplex_logic = self.custom_config.get('multiplex_logic', 'Interleave')
            multiplex_logic = 'Switch' if self.is_switch else multiplex_logic # change multiplex_logic in case of switch
            if self.multi_out: # custom logic: copy, dispatch
                if multiplex_logic == 'Interleave':
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index_push], flowItem.size) # increase buffer size
                    self._serv_buffers.lpush(self.egress[self.interleave_index_push], flowItem)
                    self.inc_interleave_index_push()
                elif multiplex_logic == 'Priority':
                    self.logger.warning('Ignoring priority for the moment, falling back to "Interleave" multiplex_logic')
                    self._buffer_metadata_interface.push_info(self.egress[self.interleave_index_push], flowItem.size) # increase buffer size
                    self._serv_buffers.lpush(self.egress[self.interleave_index_push], flowItem)
                    self.inc_interleave_index_push()
                elif multiplex_logic == 'Duplicate':
                    for key in self.egress:
                        # self._serv_buffers.lpush(key, flowItem)
                        self.push_flow_pipeline(key, flowItem)
                        self._buffer_metadata_interface.push_info(key, flowItem.size) # increase buffer size
                    pushed_count = len(self.egress)
                elif multiplex_logic == 'Switch':
                    buuids = self.egress.get(flowItem.channel, []) # drop non valid channel
                    for buuid in buuids:
                        self.push_flow_pipeline(buuid, flowItem)
                    pushed_count = len(buuids)
                    self._buffer_metadata_interface.push_info(buuid, flowItem.size*pushed_count) # increase buffer size
                else:
                    self.logger.warning('Unkown multiplexer logic')
            else: # same as simple link manager
                self._buffer_metadata_interface.push_info(self.egress[0], flowItem.size) # increase buffer size
                # self._serv_buffers.lpush(self.egress[0], flowItem)
                if pipeline:
                    self.push_flow_pipeline(self.egress[0], flowItem)
                else:
                    self._serv_buffers.lpush(self.egress[0], flowItem)

            return pushed_count
        else:
            self.logger.warning('Process wanted to push message but no egress connection(s) are registered')
            return 0

class FlowItem:
    def __init__(self, content, origin=None, raw=False, channel=0, is_json=False, redirect=False):
        if raw:
            if content is None:
                self.content = None
            else:
                jflowItem = json.loads(content)
                self.content = jflowItem['content']
                self.size = jflowItem['size']
                self.origin = jflowItem['origin']
                self.redirect = jflowItem['redirect']
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
            self.redirect = redirect
            # self.is_json = is_json

    def message(self):
        return self.content

    def __repr__(self):
        return json.dumps(objToDictionnary(self))

    def __str__(self):
        return self.__repr__()
