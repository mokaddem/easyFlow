#!/usr/bin/env python3.5

from util import genUUID
import redis, json, time, os
import shlex, subprocess

from util import genUUID, objToDictionnary
from process_print_to_console import Print_to_console
from process_metadata_interface import Process_metadata_interface, Process_representation

host='localhost'
port=6780
db=0
ALLOWED_PROCESS_TYPE = set(['print_to_console', 'print_current_time'])

class Process_manager:
    def __init__(self, processes_to_start):
        self._serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self._metadata_interface = Process_metadata_interface()
        self.processes = []
        self.processes_uuid = []

        for proc in processes_to_start:
            self.create_process(proc)

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
            print('wait_for_process_running_state')

    def process_already_started(self, puuid):
        return puuid in self.processes_uuid

    def create_process(self, data):
        puuid = data.get('puuid', None)
        if puuid is None:
            # gen process UUID
            puuid = genUUID()
            data['puuid'] = puuid

        if self.process_already_started(puuid):
            return "process already started"

        process_type = data['type']
        if process_type not in ALLOWED_PROCESS_TYPE:
            print('0 returned')
            return 0
        # gen config
        process_config = Process_representation(data)
        self._serv.set('config_'+puuid, process_config.toJSON())
        # start process with Popen
        args = shlex.split('python3 {} {}'.format(os.path.join('processes/', process_type+'.py'), puuid))
        proc = subprocess.Popen(args)
        # wait that process start the run() phase
        self.wait_for_process_running_state(puuid)
        process_config.add_subprocessObj(proc)
        self.processes.append(process_config)
        self.processes_uuid.append(puuid)
        return process_config
