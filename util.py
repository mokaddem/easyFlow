#!/usr/bin/env python3.5

import uuid
import time
import collections

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
        self.timedArray = collections.deque() # used as we will pop fom the begining -> O(1) instead of O(n)

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
