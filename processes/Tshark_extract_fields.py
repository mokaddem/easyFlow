#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process

import json
from subprocess import PIPE, Popen

# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: dict_keys([])



class Tshark_extract_fields(Process):

    def process_message(self, msg, channel):
        # msg is filepath
        self.logger.info('Processing file %s', msg)
        self.fields_from_tshark(msg, self.custom_config['fields_list'], self.custom_config['filters'])

    def fields_from_tshark(self, filepath, fields_list, filters):
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
            self.forward(dico)
            # self.forward(json.dumps(dico))
            # to_return.append(dico)
        # return to_return
        self._alert_manager.send_alert(
            title=self.name,
            content='Finished processing file {}'.format(filepath),
            mType='info',
            group='singleton'
        )



if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Tshark_extract_fields(uuid)
