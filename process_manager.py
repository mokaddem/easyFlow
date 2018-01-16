#!/usr/bin/env python3.5

from util import genUUID
import redis, json, time, os
import shlex, subprocess
import psutil, signal
import logging

from util import genUUID, objToDictionnary, Config_parser
from alerts_manager import Alert_manager
from process_print_to_console import Print_to_console
from process_metadata_interface import Process_metadata_interface, Process_representation, Link_representation, Buffer_metadata_interface
easyFlow_conf = os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')

class Process_manager:
    def __init__(self, projectUUID):
        logging.basicConfig(format='%(levelname)s[%(asctime)s]: %(message)s')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s[%(asctime)s]: %(message)s')
        self.log_handler = logging.FileHandler(os.path.join(os.environ['FLOW_LOGS'], 'project.log'))
        self.log_handler.setLevel(logging.INFO)
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

        self.config = Config_parser(easyFlow_conf, projectUUID).get_config()
        try:
            self._serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.warning('Redis unix_socket not used for projects, falling back to TCP')
            self._serv = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)
        try:
            self._serv_buffers = redis.Redis(unix_socket_path=self.config.redis.buffers.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.warning('Redis unix_socket not used fo buffering, falling back to TCP')
            self._serv_buffers = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)

        self._metadata_interface = Process_metadata_interface()
        self._buffer_metadata_interface = Buffer_metadata_interface()
        self._alert_manager = Alert_manager()
        self._being_restarted = []
        self.processes = {}
        self.processes_uuid = []
        self.processes_uuid_with_signal = []
        self.buffers = {}
        self.buffers_uuid = []
        self.projectUUID = projectUUID


    def start_processes(self, processes_to_start, buffers_to_register):
        l = len(processes_to_start)
        if l>0:
            self.push_starting_all_processes(l);
            # start processes
            for puuid, procData in processes_to_start.items():
                time.sleep(0.1)
                self.create_process(procData, puuid)

            # register buffers
            for buuid, bufData in buffers_to_register.items():
                buffer_config = Link_representation(bufData)
                self.buffers[buuid] = buffer_config
                self.buffers_uuid.append(buuid)

    def get_connected_buffers(self, puuid):
        self.logger.debug('Getting connected buffers of process "%s" [%s]', self.processes[puuid].name, puuid)
        buuids = []
        for buuid, buf in self.buffers.items():
            if (puuid in buf.fromUUID) or (puuid in buf.toUUID):
                buuids.append(buuid)
        return buuids

    def get_processes_info(self):
        self.logger.debug('Getting processes info')
        info = []
        for puuid in self.processes_uuid:
            pinfo = self._metadata_interface.get_info(puuid)
            info.append(pinfo)
        return info

    def get_buffers_info(self):
        self.logger.debug('Getting buffers info')
        info = []
        for buuid in self.buffers_uuid:
            binfo = objToDictionnary(self.buffers[buuid])
            realtime_binfo = self._buffer_metadata_interface.get_info(buuid) # realtime info
            binfo['stats'] = realtime_binfo
            info.append(binfo)
        return info

    # A process terminate its setup when its config key is deleted
    def wait_for_process_running_state(self, puuid):
        self.logger.debug('Waiting for process "%s" [%s] to run', self.processes[puuid].name, puuid)
        while True:
            if not self._serv.exists('config_'+puuid):
                break
            time.sleep(0.1)

    def process_started_and_managed(self, puuid):
        managed = puuid in self.processes_uuid
        return managed and (puuid not in self._being_restarted)

    def process_started_in_system(self, puuid, killIt=False):
        for p in psutil.process_iter(attrs=['name', 'cmdline']):
            if (puuid in p.info['name']) or (puuid in p.info['cmdline']):
                if killIt:
                    _, alive = psutil.wait_procs([p], timeout=1)
                    if len(alive) > 0: # process not killed -> force kill
                        alive[0].kill()
                return [True, p.pid]
        return [False, 0]

    def push_starting_all_processes(self, count):
        self.logger.info('Starting all processes (%s process(es))', count)
        self._alert_manager.send_alert(
            title='Processes',
            content='starting all processes',
            mType='info',
            group=self.projectUUID+'_processes',
            totalCount=count
        )

    def is_multiplexer(self, puuid):
        return self.processes[puuid].is_multiplexer

    def shutdown(self):
        self.logger.info('Shutting down all processes (%s process(es))')
        for puuid in self.processes.keys():
            self.kill_process(puuid)

    def reload_states(self, process_uuids):
        for puuid in process_uuids:
            self.send_command(puuid, 'reload')

        for puuid in [p for p in process_uuids if p in self.processes_uuid_with_signal]:
            # send signal to the module
            self.logger.debug('Sending signal to %s [%s]', self.processes[puuid].name, puuid)
            self.processes[puuid]._subprocessObj.send_signal(signal.SIGUSR1)

    def pause_process(self, puuid):
        self.logger.info('Pausing process "%s" [%s]', self.processes[puuid].name, puuid)
        self.send_command(puuid, 'pause')
    def play_process(self, puuid):
        self.logger.info('Playing process "%s" [%s]', self.processes[puuid].name, puuid)
        self.send_command(puuid, 'play')
    def restart_process(self, puuid):
        self.logger.info('Restarting process "%s" [%s]', self.processes[puuid].name, puuid)
        pData = self.processes[puuid].get_dico()
        self._alert_manager.send_alert(
            title='Processes',
            content='restarting '+pData['name'],
            mType='warning'
        )
        self._being_restarted.append(puuid)
        self.kill_process(puuid)
        self.create_process(pData, puuid)
        self._being_restarted.remove(puuid)

    def send_command(self, puuid, command, data=None):
        self.logger.info('Sending command (%s) to process "%s" [%s]', command, self.processes[puuid].name, puuid)
        jCommand = {}
        jCommand['operation'] = command
        jCommand['data'] = data
        keyCommands = 'command_'+puuid
        process_config = self.processes[puuid]
        self._serv.set('config_'+puuid, process_config.toJSON())
        self._serv.lpush(keyCommands, json.dumps(jCommand))

    def should_send_signal(self, process_type):
        MODULE_WITH_SIGNAL = ['generate_lorem_ipsum']
        if process_type in MODULE_WITH_SIGNAL:
            return True

    def kill_process(self, puuid):
        subProcObj = self.processes[puuid]._subprocessObj
        self.logger.info('Killing process "%s" [%s, pid=%s]', self.processes[puuid].name, puuid, subProcObj.pid)
        subProcObj.terminate()
        self._serv.delete(puuid)

    def create_process(self, data, puuid=None):
        if puuid is None:
            puuid = data.get('puuid', None)
            if puuid is None:
                # gen process UUID
                puuid = 'process_'+genUUID()
        data['puuid'] = puuid
        data['projectUUID'] = self.projectUUID

        if self.process_started_and_managed(puuid):
            return ""

        # pStarted, pid = self.process_started_in_system(puuid, killIt=False)
        pStarted, pid = self.process_started_in_system(puuid, killIt=True)
        if pStarted:
            self.logger.info('Process "%s" [%s, pid=%s] was already started', data.get('name', None), puuid, pid)
            self._alert_manager.send_alert(title='Process',
                content='{} was started in system (pid={}). Trying to recover state...'.format(data.get('name', None), pid),
                mType='warning', group='singleton')
            process_config = Process_representation(data)
            process_config.add_subprocessObj(psutil.Process(pid))
            self.processes[puuid] = process_config
            self.processes_uuid.append(puuid)
            if self.should_send_signal(process_config.type):
                self.processes_uuid_with_signal.append(puuid)
            return process_config

        else:
            process_type = data['type']
            allowed_scripts = [ s.rstrip('.py') for s in self.config.processes.allowed_script]
            if process_type not in allowed_scripts:
                return 0
            # gen config
            process_config = Process_representation(data)
            self._serv.set('config_'+puuid, process_config.toJSON())
            # start process with Popen
            args = shlex.split('python3.5 {} {}'.format(os.path.join(os.environ['FLOW_PROC'], process_type+'.py'), puuid))
            proc = psutil.Popen(args)
            self.logger.info('Creating new process "%s" [pid=%s] ', data.get('name', 'NO_NAME'), proc.pid)
            # wait that process start the run() phase, publish info
            # self.wait_for_process_running_state(puuid)

            process_config.add_subprocessObj(proc)
            self.processes[puuid] = process_config
            self.processes_uuid.append(puuid)
            if self.should_send_signal(process_type):
                self.processes_uuid_with_signal.append(puuid)
            return process_config

    def delete_process(self, puuid):
        self.logger.info('Deleting process %s [%s]', self.processes[puuid].name, puuid)
        self.kill_process(puuid)
        self.processes_uuid.remove(puuid)
        try:
            self.processes_uuid_with_signal.remove(puuid)
        except ValueError as e:
            pass
        del self.processes[puuid]
        # delete residual keys in redis
        keys = self._serv.keys('*{}*'.format(puuid))
        for k in keys:
            self._serv.delete(k)
        # also remove links
        buuids = self.get_connected_buffers(puuid)
        for buuid in buuids:
            self.delete_link(buuid)

    def update_process(self, data):
        puuid = data.get('puuid', None)
        if puuid is None:
            return {'state': 'error: puuid is None'}
        self.processes[puuid].update(data)
        self.logger.debug('Updated process "%s" [%s]', self.processes[puuid].name, puuid)
        return self.processes[puuid]


    def create_link(self, data, buuid=None):
        if buuid is None:
            buuid = data.get('buuid', None)
            if buuid is None:
                # gen buffer UUID
                buuid = 'buffer_'+genUUID()
        data['buuid'] = buuid
        data['projectUUID'] = self.projectUUID

        buffer_type = data['type']
        if buffer_type not in self.config.buffers.allowed_buffer_type:
            self.logger.info('Unknown buffer type: %s', buffer_type)
            return 0
        self.logger.info('Creating new %s buffer: %s', buffer_type, data.get('name', 'unamed'))
        # gen config
        buffer_config = Link_representation(data)
        self._serv.set('config_'+buuid, buffer_config.toJSON())

        # add it to self.buffers
        self.buffers[buuid] = buffer_config
        # add it to self.buffers_uuid
        self.buffers_uuid.append(buuid)
        return buffer_config

    def delete_link(self, buuid):
        self.logger.info('Deleting buffer %s', self.buffers[buuid].name)
        self.buffers_uuid.remove(buuid)
        del self.buffers[buuid]
        # delete residual keys in redis
        keys = self._serv.keys('*{}*'.format(buuid))
        for k in keys:
            self._serv.delete(k)
        keys = self._serv_buffers.keys('*{}*'.format(buuid))
        for k in keys:
            self._serv_buffers.delete(k)
