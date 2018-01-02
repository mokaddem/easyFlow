#!/usr/bin/env python3.5

import json
import redis
from util import genUUID

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
        puuid = pMetadata['uuid']
        self._serv.set(puuid, jMetadata)
