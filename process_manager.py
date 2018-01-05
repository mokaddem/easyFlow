#!/usr/bin/env python3.5

from util import genUUID
import redis, json, time, os
import shlex, subprocess
import psutil

from util import genUUID, objToDictionnary
from alerts_manager import Alert_manager
from process_print_to_console import Print_to_console
from process_metadata_interface import Process_metadata_interface, Process_representation, Link_representation

host='localhost'
port=6780
db=0
ALLOWED_PROCESS_TYPE = set(['print_to_console', 'print_current_time'])
ALLOWED_BUFFER_TYPE = set(['FIFO', 'LIFO'])

class Process_manager:
    def __init__(self, projectUUID):
        self._serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
        self._metadata_interface = Process_metadata_interface()
        self._alert_manager = Alert_manager()
        self.processes = {}
        self.processes_uuid = []
        self.projectUUID = projectUUID

        # self.start_processes(processes_to_start)

    def start_processes(self, processes_to_start):
        l = len(processes_to_start)
        if l>0:
            self.push_starting_all_processes(l);
            for puuid, proc in processes_to_start.items():
                time.sleep(0.1)
                self.create_process(proc, puuid)
            self._alert_manager.send_alert(
                title='Hoy',
                content='System is ready and running!',
                mType='success',
                group='singleton'
            )

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
            # time.sleep(0.1)
            time.sleep(1)
            print('wait_for_process_running_state')

    def process_started_and_managed(self, puuid):
        return puuid in self.processes_uuid

    def process_started_in_system(self, puuid, killIt=False):
        for p in psutil.process_iter(attrs=['name', 'cmdline']):
            if (puuid in p.info['name']) or (puuid in p.info['cmdline']):
                if killIt:
                    _, alive = psutil.wait_procs([p], timeout=1)
                if len(alive) > 0: # process not killed -> force kill
                    alive[0].kill()
                return True
        return False

    def push_starting_all_processes(self, count):
        self._alert_manager.send_alert(
            title='Processes',
            content='starting all processes',
            mType='info',
            group=self.projectUUID+'_processes',
            totalCount=count
        )

    def shutdown(self):
        for puuid, proc in self.processes.items():
            subProcObj = proc._subprocessObj
            subProcObj.terminate()

    def create_process(self, data, puuid=None):
        if puuid is None:
            puuid = data.get('puuid', None)
            if puuid is None:
                # gen process UUID
                puuid = genUUID()
        data['puuid'] = puuid
        data['projectUUID'] = self.projectUUID

        if self.process_started_and_managed(puuid):
            return "process already started"
        elif self.process_started_in_system(puuid, killIt=True):
            print("process was started in system")
            self._alert_manager.send_alert(title='Process',
                content='Process {} was started in system and has been killed'.format(data.get('name', None)),
                mType='warning', group='singleton')

        process_type = data['type']
        if process_type not in ALLOWED_PROCESS_TYPE:
            print('Unkown process type')
            return 0
        # gen config
        process_config = Process_representation(data)
        self._serv.set('config_'+puuid, process_config.toJSON())
        # start process with Popen
        args = shlex.split('python3 {} {}'.format(os.path.join('processes/', process_type+'.py'), puuid))
        proc = subprocess.Popen(args)
        # wait that process start the run() phase, publish info
        self.wait_for_process_running_state(puuid)

        process_config.add_subprocessObj(proc)
        self.processes[puuid] = process_config
        self.processes_uuid.append(puuid)
        return process_config

    def delete_process(self, puuid):
        proc = self.processes[puuid]
        subProcObj = proc._subprocessObj
        subProcObj.terminate()
        self.processes_uuid.remove(puuid)
        del self.processes[puuid]
        # also remove links


    def create_link(self, data, buuid=None):
        if buuid is None:
            buuid = data.get('buuid', None)
            if buuid is None:
                # gen buffer UUID
                buuid = genUUID()
        data['buuid'] = buuid
        data['projectUUID'] = self.projectUUID

        buffer_type = data['type']
        if buffer_type not in ALLOWED_BUFFER_TYPE:
            print('Unkown buffer type')
            return 0
        # gen config
        buffer_config = Link_representation(data)
        self._serv.set('config_'+buuid, buffer_config.toJSON())

        # add it to self.buffers ???
        # add it to self.buffers_uuid ????
        return buffer_config
