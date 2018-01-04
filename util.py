#!/usr/bin/env python3.5

import uuid

def genUUID():
    return str(uuid.uuid4())

def objToDictionnary(obj, full=False):
    ret = {}
    # print(type(obj))
    for attr, value in obj.__dict__.items():
        if not full and attr.startswith('_'):
            continue
        #recursive
        if type(value) is dict:
            ret[attr] = dicoToList(value)
        elif type(value) is list:
            ret[attr] = listToDictionnary(value)
        else:
            ret[attr] = value
    return ret

def listToDictionnary(list, full=False):
    ret = []
    for elem in list:
        ret.append(dicoToList(elem))
    return ret

def dicoToList(dic):
    ret = []
    for k, v in dic.items():
        ret.append(v)
    return ret
