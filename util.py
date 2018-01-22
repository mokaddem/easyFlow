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
    def __init__(self, resolution):
        self.timedDico = {}
        self.resolution = int(resolution)
        self.baseTime = int(time.time())

    def add(self, element):
        now = int(time.time())
        offset_to_be_placed = int((now - self.baseTime)/self.resolution)
        index_to_be_placed = self.baseTime + self.resolution*offset_to_be_placed
        if index_to_be_placed not in self.timedDico:
            self.timedDico[index_to_be_placed] = 0
        self.timedDico[index_to_be_placed] += 1

    def get_sum(self, timerange=20):
        return sum([ v for t,v in self.get_history(timerange) ])

    def get_history(self, timerange=20):
        ret = []
        now = int(time.time())
        current_offset = int((now - self.baseTime)/self.resolution)
        current_index = self.baseTime + self.resolution*current_offset
        for cTime in range(current_index-timerange*self.resolution, current_index+self.resolution, self.resolution):
            val = self.timedDico.get(cTime, 0)
            ret.append([cTime, val])
        return ret

class SummedTimeSpanningArray(TimeSpanningArray):
    def __init__(self, resolution):
        super().__init__(resolution)
        self.sumedDico = {}

    def add(self, element):
        super().add(element)
        now = int(time.time())
        offset_to_be_placed = int((now - self.baseTime)/self.resolution)
        index_to_be_placed = self.baseTime + self.resolution*offset_to_be_placed
        if index_to_be_placed not in self.sumedDico:
            self.sumedDico[index_to_be_placed] = 0
        self.sumedDico[index_to_be_placed] += int(element)

    def get_history(self, timerange=20):
        ret = []
        now = int(time.time())
        current_offset = int((now - self.baseTime)/self.resolution)
        current_index = self.baseTime + self.resolution*current_offset
        for cTime in range(current_index-timerange*self.resolution, current_index+self.resolution, self.resolution):
            val = self.sumedDico.get(cTime, 0)
            ret.append([cTime, val])
        return ret
