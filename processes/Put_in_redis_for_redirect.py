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


    def before_sleep(self):
        self._database_pipeline.execute()

    def process_message(self, msg, **kargs):
        keyname = self.prepend_keyname+'_'+genUUID()
        # self._database_server.set(keyname, msg)

        self._database_pipeline.set(keyname, msg)
        if self.pipeline_counter >= 16:
            self._database_pipeline.execute()
            self.pipeline_counter = 0
        else:
            self.pipeline_counter += 1

        complete_path_redirect = 'redis@'+keyname

        del kargs['redirect']
        self.forward(complete_path_redirect, pipeline=True, redirect=True, **kargs)


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Put_in_redis_for_redirect(uuid)
