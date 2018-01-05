#!/usr/bin/env python3.5

import json
import redis
from util import genUUID, objToDictionnary

host='localhost'
port=6780
db=0

''' for now, raw json in redis '''
class Process_metadata_interface:
    def __init__(self):
        self._serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)


    def get_info(self, puuid):
        jMetadata = self._serv.get(puuid)
        pMetadata = json.loads(jMetadata)
        return pMetadata

    def push_info(self, pMetadata):
        jMetadata = json.dumps(pMetadata)
        puuid = pMetadata['puuid']
        self._serv.set(puuid, jMetadata)


class Process_representation:
    def __init__(self, data):
        self.puuid = data['puuid']
        self.x = data['x']
        self.y = data['y']
        self.name = data['name']
        self.type = data['type']
        self.description = data['description']
        self.bulletin_level = data['bulletin_level']
        self.connections = data.get('connections', [])
        self._subprocessObj = data.get('subprocessObj', None)
        self.projectUUID = data['projectUUID']

    def gen_process_config(self):
        return objToDictionnary(self, full=False)

    def add_subprocessObj(self, proc):
        self._subprocessObj = proc

    def __repr__(self):
        return json.dumps(objToDictionnary(self, full=False))

    def __str__(self):
        return self.__repr__()

    def toJSON(self):
        # return json.dumps(self, default=lambda o: o.__dict__)
        return self.__repr__()

    def get_dico(self):
        return self.gen_process_config()

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
        # return json.dumps(self, default=lambda o: o.__dict__)
        return self.__repr__()

    def get_dico(self):
        return self.gen_buffer_config()
