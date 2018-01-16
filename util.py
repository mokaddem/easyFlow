#!/usr/bin/env python3.5

import uuid
import time, json
from collections import deque, namedtuple

class Config_parser:
    def __init__(self, filename, projectUUID=None):
        import redis

        self.filename = filename
        with open(filename, 'r') as f:
            raw_config = f.read()
            self.config_json = json.loads(raw_config)

            if projectUUID is not None:
                try:
                    serv = redis.Redis(unix_socket_path=self.config_json['redis']['project']['unix_socket_path'], decode_responses=True)
                except: # fallback using TCP instead of unix_socket
                    serv = redis.StrictRedis(
                        self.config_json['redis']['project']['host'],
                        self.config_json['redis']['project']['port'],
                        self.config_json['redis']['project']['db'],
                        charset="utf-8", decode_responses=True)
                rawJSONProject = serv.get(projectUUID)
                jProject = json.loads(rawJSONProject)
                project_config = jProject.get('project_config', None)
                # replace "default_project" if defined in the project itself
                if project_config is not None:
                    self.config_json['default_project'] = jProject['project_config']

            # self.config = json.loads(self.config_json, object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))
            self.config = json.loads(json.dumps(self.config_json), object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))

    def get_config(self):
        return self.config

    def __str__(self):
        return self.config_json

def genUUID():
    return str(uuid.uuid4())

def datetimeToTimestamp(datetimeObj):
    return int(time.mktime(datetimeObj.timetuple()))

def objToDictionnary(obj, full=False, to_ignore=[]):
    ret = {}
    # print(type(obj))
    for attr, value in obj.__dict__.items():
        if not full and attr.startswith('_') or attr in to_ignore:
            continue
        #recursive
        if type(value) is dict:
            # ret[attr] = dicoToList(value)
            ret[attr] = value
        elif type(value) is list:
            ret[attr] = listToDictionnary(value)
        else:
            ret[attr] = value
    return ret

def listToDictionnary(l, full=False):
    ret = []
    for elem in l:
        ret.append(dicoToList(elem))
    return ret

def dicoToList(dic):
    ret = []
    for k, v in dic.items():
        ret.append(v)
    return ret

class TimeSpanningArray:
    def __init__(self, lifetime):
        self.lifetime = lifetime
        self.timedArray = deque() # used as we will pop fom the begining -> O(1) instead of O(n)

    def add(self, element):
        now = time.time()
        self.timedArray.append([now, element])

    def get(self):
        self.enforce_consistency()
        return list(self.timedArray)

    def enforce_consistency(self):
        lower_bound = time.time() - self.lifetime
        index_offset = 0 # if we remove an element, the iterating index value must be adjusted
        for i in range(len(self.timedArray)):
            if self.timedArray[i-index_offset][0] < lower_bound: # need to remove element
                self.timedArray.popleft()
                index_offset += 1
            else: # array is sorted, no need to continue
                break

class SummedTimeSpanningArray(TimeSpanningArray):
    def __init__(self, lifetime):
        super().__init__(lifetime)
        self.sum = 0

    def add(self, element):
        super().add(element)
        self.sum += element

    def get_sum(self):
        self.enforce_consistency()
        return self.sum

    def enforce_consistency(self):
        lower_bound = time.time() - self.lifetime
        index_offset = 0 # if we remove an element, the iterating index value must be adjusted
        for i in range(len(self.timedArray)):
            t, element = self.timedArray[i-index_offset]
            if t < lower_bound: # need to remove element
                self.sum -= element
                self.timedArray.popleft()
                index_offset += 1
            else: # array is sorted, no need to continue
                break
