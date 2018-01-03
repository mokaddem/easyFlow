#!/usr/bin/env python3.5

from util import genUUID
import redis, json, time, os
import shlex, subprocess

from process_print_to_console import Print_to_console
from process_metadata_interface import Process_metadata_interface

host='localhost'
port=6780
db=0
ALLOWED_PROCESS_TYPE = set(['print_to_console', 'print_current_time'])

class Process_manager:
    def __init__(self):
        self._serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self._metadata_interface = Process_metadata_interface()
        self.processes = []
        self.processes_uuid = []

    def get_processes_info(self):
        info = []
        for puuid in self.processes_uuid:
            pinfo = self._metadata_interface.get_info(puuid)
            info.append(pinfo)
        return info

    # A process terminate its setup when its config key is deleted
    def wait_for_process_running_state(self, puuid):
        while True:
            if not self._serv.exists('config_'+puuid):
                break
            time.sleep(0.1)
            print('sleeping')


    def create_process(self, data):
        # gen process UUID
        puuid = genUUID()
        data['uuid'] = puuid
        process_type = data['type']
        if process_type not in ALLOWED_PROCESS_TYPE:
            print('0 returned')
            return 0
        # put process config in redis_config
        self._serv.set('config_'+puuid, json.dumps(data))
        # start process with Popen
        args = shlex.split('python3 {} {}'.format(os.path.join('processes/', process_type+'.py'), puuid))
        print(args)
        proc = subprocess.Popen(args)
        # wait that process start the run() phase
        self.wait_for_process_running_state(puuid)
        self.processes.append(proc)
        self.processes_uuid.append(puuid)
        return puuid

    def applyOperation(self, operation, data):
        if operation == 'create_process':
            response = {'status': 'success'}
            response['id'] = genUUID()
            if data.get('x', None) is None or data.get('y', None) is None:
                response['x'] = 0; response['y'] = 0
            else:
                response['x'] = data.get('x'); response['y'] = data.get('y')
            response['name'] = data.get('name', None)
            response['type'] = data.get('type', None)
            response['description'] = data.get('description', '')
            response['bulletin_level'] = data.get('bulletin_level', None)

            return response

        elif operation == 'add_link':
            response = {'status': 'success'}
            response['id'] = genUUID()
            return response

        elif operation == 'update':
            return {'status': 'error' }
        else:
            return {'status': 'error' }
