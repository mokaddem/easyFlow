#!/usr/bin/env python3.5

import uuid

def genUUID():
    return str(uuid.uuid4())

def objToDictionnary(obj):
    ret = {}
    for attr, value in obj.__dict__.items():
        if attr.startswith('_'):
            continue
        ret[attr] = value
    return ret
