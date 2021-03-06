#!/usr/bin/env python3.5

import os
import json
import redis
from util import genUUID, objToDictionnary, Config_parser
easyFlow_conf = os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')

''' for now, raw json in redis '''
class Process_metadata_interface:
    def __init__(self):
        self.config = Config_parser(easyFlow_conf).get_config()
        try:
            self._serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._serv = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)


    def get_info(self, puuid):
        jMetadata = self._serv.get(puuid)
        if jMetadata is None:
            return {}
        pMetadata = json.loads(jMetadata)
        return pMetadata

    def push_info(self, pMetadata):
        jMetadata = json.dumps(pMetadata)
        puuid = pMetadata['puuid']
        self._serv.set(puuid, jMetadata)

    def clear_info(self, puuid):
        self._serv.delete(puuid)

# Do not use JSON as a buffer is updated by the pushing process and the poping process
class Buffer_metadata_interface:
    def __init__(self):
        self.config = Config_parser(easyFlow_conf).get_config()
        try:
            self._serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._serv = redis.StrictRedis(
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

    def get_info(self, buuid):
        bMetadata = {
            'buffered_bytes': self._serv.get(buuid+'_buffered_bytes'),
            'buffered_flowItems': self._serv_buffers.llen(buuid)
        }
        return bMetadata

    def push_info(self, buuid, the_bytes):
        self._serv.incrby(buuid+'_buffered_bytes', the_bytes)

    def clear_info(self, buuid):
        self._serv.delete(buuid+'_buffered_bytes'),
        self._serv_buffers.delete(buuid)

class Process_representation:
    def __init__(self, data):
        self.puuid = data['puuid']
        self.x = data['x']
        self.y = data['y']
        self.name = data['name']
        self.type = data['type']
        self.description = data['description']
        self.bulletin_level = data['bulletin_level']
        self.custom_config = data.get('custom_config', {})
        self._subprocessObj = data.get('subprocessObj', None) # /!\ may be a subprocess or psutil object
        self.projectUUID = data['projectUUID']
        self.is_multiplexer = self.type in ["multiplexer_out", "multiplexer_in"]

    def update(self, data):
        self.name = data['name']
        self.type = data['type']
        self.description = data['description']
        self.bulletin_level = data['bulletin_level']
        self.custom_config = data.get('custom_config', {})

    def gen_process_config(self):
        return objToDictionnary(self, full=False)

    def add_subprocessObj(self, proc):
        self._subprocessObj = proc

    def __repr__(self):
        return json.dumps(objToDictionnary(self, full=False))

    def __str__(self):
        return self.__repr__()

    def toJSON(self):
        return self.__repr__()

    def get_dico(self):
        return self.gen_process_config()

    @staticmethod
    def getEmptyInfo(projectUUID, puuid):
        ret = {}
        ret['puuid'] = puuid
        ret['name'] = None
        ret['type'] = None
        ret['description'] = None
        ret['custom_config'] = {}
        ret['config'] = {}
        ret['projectUUID'] = projectUUID
        ret['is_multiplexer'] = None
        ret['stats'] = {}
        return ret

class Link_representation:
    def __init__(self, data):
        self.buuid = data['buuid']
        self.name = data['name']
        self.x = data['x']
        self.y = data['y']
        self.type = data['type']
        self.description = data['description']
        self.projectUUID = data['projectUUID']
        self.fromUUID = data['fromUUID']
        self.toUUID = data['toUUID']

    def gen_buffer_config(self):
        return objToDictionnary(self, full=False)

    def __repr__(self):
        return json.dumps(objToDictionnary(self, full=False))

    def __str__(self):
        return self.__repr__()

    def toJSON(self):
        return self.__repr__()

    def get_dico(self):
        return self.gen_buffer_config()
