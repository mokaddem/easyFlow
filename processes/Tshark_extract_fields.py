#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

import json
import uuid as uuid_lib
from subprocess import PIPE, Popen
import shlex
import errno

# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: dict_keys([])

def genUUID():
    return str(uuid_lib.uuid4())

def generate_redis_proto(cmd, key, value):
    cmd_split = cmd.split()
    proto = '*{argNum}\r\n'.format(argNum=3)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(cmd), arg=cmd)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(key), arg=key)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(value), arg=value)
    return proto

class Tshark_extract_fields(Process):

    def process_message(self, msg, **kargs):
        # msg is filepath
        self.logger.info('Processing file %s', msg)
        self.fields_from_tshark(msg, self.custom_config['fields_list'], self.custom_config['filters'], **kargs)

    def fields_from_tshark(self, filepath, fields_list, filters, **kargs):
        filepath = filepath.strip()
        to_return = []

        fields_list = fields_list.split(',')

        tshark_command = ['tshark',  '-r', filepath, '-T', 'ek']
        # generate command to send with correct fields filter
        # filters and comma separeted
        for f in fields_list:
            if f == 'timestamp': # timestamp is always present in tshark output
                continue
            tshark_command += ['-e', f]
        if filters != "":
            tshark_command += ['\"'+filters+'\"']

        put_in_redis_directly = self.custom_config['put_in_redis_directly']
        if put_in_redis_directly:
            args = shlex.split('/home/sami/git/redis/src/redis-cli -h {host} -p {port} -n {db} --pipe'.format(
                host=self.config.redis.redirected_data.host,
                port=self.config.redis.redirected_data.port,
                db=self.config.redis.redirected_data.db))
            p_mass_insert = Popen(args, stdin=PIPE, universal_newlines=True)

            del kargs['redirect']

        p = Popen(tshark_command, stdin=PIPE, stdout=PIPE)

        for raw_resp in p.stdout:
            # ignore empty lines
            if raw_resp == b'\n':
                continue
            # ignore index lines
            if raw_resp[:10] == b'{"index" :':
                continue

            # done in loop for faster processing
            json_resp = json.loads(raw_resp.decode('utf8'))
            dico = {}
            json_layer = json_resp['layers']
            for f in fields_list:
                if f == 'timestamp':
                    dico[f] = json_resp[f] # wanted value is in an array, take the 1 element
                    continue

                key = f.replace('.', '_') # json key do not contain '.' they are replaced by '_'

                try:
                    dico[f] = json_layer[key][0] # wanted value is in an array, take the 1 element
                except KeyError: # sometimes fields are not present in the json
                    dico[f] = ""

            if put_in_redis_directly:
                keyname = 'redirect_tshark'+':'+genUUID()
                complete_path_redirect = 'redis@'+keyname
                # buffer_to_push = self._link_manager.egress # monolink
                proto_cmd = generate_redis_proto(cmd='SET', key=keyname, value=json.dumps(dico))
                try:
                    p_mass_insert.stdin.write(proto_cmd)
                    self.forward(complete_path_redirect, pipeline=True, redirect=True, **kargs)
                except IOError as e:
                    if e.errno == errno.EPIPE or e.errno == errno.EINVAL:
                        # Stop loop on "Invalid pipe" or "Invalid argument".
                        # No sense in continuing with broken pipe.
                        break
                    else:
                        # Raise any other error.
                        raise

            else:
                self.forward(json.dumps(dico), pipeline=True, **kargs)
            # self.forward(dico, **kargs)
            # to_return.append(dico)
        # return to_return
        self._alert_manager.send_alert(
            title=self.name,
            content='Finished processing file {}'.format(filepath),
            mType='info',
            group='singleton'
        )

        p_mass_insert.stdin.close()
        p_mass_insert.wait()


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Tshark_extract_fields(uuid)
