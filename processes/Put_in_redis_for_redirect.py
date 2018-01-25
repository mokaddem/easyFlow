#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process
import uuid as uuid_lib
import redis


# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: dict_keys(['host', 'port', 'prepend_keyname', 'db'])

def genUUID():
    return str(uuid_lib.uuid4())

class Put_in_redis_for_redirect(Process):

    def pre_run(self):
        try:
            self._database_server = redis.Redis(unix_socket_path=self.custom_config['unix_socket'], decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self._database_server = redis.StrictRedis(
                self.custom_config['host'],
                self.custom_config['port'],
                self.custom_config['db']
            )
        self._database_pipeline = self._database_server.pipeline()
        self.prepend_keyname = self.custom_config['prepend_keyname']
        self.pipeline_counter = 0
        self._to_forward = []

    def before_sleep(self):
        self._database_pipeline.execute()
        # only forward when items has been saved in the redirect database
        for item, kargs in self._to_forward:
            del kargs['redirect']
            self.forward(item, pipeline=True, redirect=True, **kargs)
        self._to_forward = []

    def process_message(self, msg, **kargs):
        keyname = self.prepend_keyname+'_'+genUUID()
        # self._database_server.set(keyname, msg)

        self._database_pipeline.set(keyname, msg)
        complete_path_redirect = 'redis@'+keyname
        self._to_forward.append([complete_path_redirect, kargs])

        if self.pipeline_counter >= 400:
            self._database_pipeline.execute()
            self.pipeline_counter = 0
            # only forward when items has been saved in the redirect database
            for item, kargs in self._to_forward:
                del kargs['redirect']
                self.forward(item, pipeline=True, redirect=True, **kargs)
            self._to_forward = []
        else:
            self.pipeline_counter += 1


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Put_in_redis_for_redirect(uuid)
