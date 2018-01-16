#!/usr/bin/env python3.5
import json
import redis
import time, os
from util import genUUID, objToDictionnary, Config_parser
easyFlow_conf = os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')

''' for now, raw json in redis '''
class Alert_manager:
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

    def subscribe(self):
        self.pmanager_pubsub = self._serv.pubsub(ignore_subscribe_messages=True)
        self.pmanager_pubsub.subscribe('alert_stream')

    def make_response_stream(self):
        self.subscribe()
        for message in self.pmanager_pubsub.listen():
            messageData = json.loads(message['data'])
            title = messageData['title']
            content = messageData['message']
            mType = messageData['mType']
            group = messageData['group']
            totalCount = messageData.get('totalCount', 0)
            resp = {
                'title': title,
                'message': content,
                'type': mType,
                'group': group,
                'totalCount': totalCount
            }
            yield 'data: %s\n\n' % json.dumps(resp)


    def send_alert(self, title='', content='', mType='info', group='singleton', totalCount=0):
        resp = {
            'title': title,
            'message': content,
            'mType': mType,
            'group': group,
            'totalCount': totalCount
        }
        self._serv.publish('alert_stream', json.dumps(resp))
