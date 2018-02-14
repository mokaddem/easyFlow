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

        self.config = Config_parser(easyFlow_conf, projectUUID).get_config()

        logging.basicConfig(format='%(levelname)s[%(asctime)s]: %(message)s')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.default_project.process_manager.log_level))
        formatter = logging.Formatter('%(levelname)s[%(asctime)s]: %(message)s')
        self.log_handler = logging.FileHandler(os.path.join(os.environ['FLOW_LOGS'], 'project.log'))
        self.log_handler.setLevel(getattr(logging, self.config.default_project.process_manager.log_level))
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

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

        self.boostraping = False # prevent multiple startAll
        self.shutting_down_phase = False

        self._metadata_interface = Process_metadata_interface()
        self._buffer_metadata_interface = Buffer_metadata_interface()
        self._alert_manager = Alert_manager()
        self._being_restarted = []
        self.processes = {}
        self.processes_uuid = set()
        self.processes_uuid_with_signal = set()
        self.buffers = {}
        self.buffers_uuid = set()
        self.projectUUID = projectUUID

        self.puuid_to_be_restarted = {}


    def start_processes(self, processes_to_start, buffers_to_register):
        l = len(processes_to_start)
        if l>0:
            self.push_starting_all_processes(l);
            self.boostraping = True
            # start processes
            for puuid, procData in processes_to_start.items():
                time.sleep(0.1)
                self.create_process(procData, puuid)

            # register buffers
            for buuid, bufData in buffers_to_register.items():
                # delete any state before starting
                self._buffer_metadata_interface.clear_info(buuid)
                buffer_config = Link_representation(bufData)
                self.buffers[buuid] = buffer_config
                self.buffers_uuid.add(buuid)

            self.boostraping = False

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
        process_uuids_to_be_force_reloaded = []
        for puuid in self.processes_uuid:

            pinfo = self._metadata_interface.get_info(puuid)

            now = time.time()
            if pinfo == {}:  # no info for the moment OR impossible to start module
                self.logger.info('No process info for the moment for "%s" [%s]', self.processes[puuid].name, puuid)
                if puuid in self.puuid_to_be_restarted:
                    self.logger.info('"%s" [%s]: %ssec until force restart', self.processes[puuid].name, puuid, self.puuid_to_be_restarted[puuid] - now)
                    if self.puuid_to_be_restarted[puuid] >= now:
                        self.logger.info('Process "%s" [%s] still not send information. Forcing restart', self.processes[puuid].name, puuid)
                        process_uuids_to_be_force_reloaded.append(puuid)
                        del self.puuid_to_be_restarted[puuid]
                else:
                    self.puuid_to_be_restarted[puuid] = now + self.config.processes.force_restart

            else:
                if (now - pinfo.get('representationTimestamp', 0)) > self.config.processes.force_pushing_state_interval: # if no info received from a long time, send a signal to the process
                    self.logger.info('Process "%s" [%s, pid=%s] did not send info data since %s seconds',
                        pinfo['name'], pinfo['puuid'], pinfo['pid'],
                        self.config.processes.force_pushing_state_interval)
                    process_uuids_to_be_force_reloaded.append(puuid)
                    # if process did not get reloaded, setting its state to crashed
                    if (now - pinfo['representationTimestamp']) > (self.config.processes.force_pushing_state_interval + 2*self.config.web.refresh_metadata_interval_in_sec):
                        pinfo['stats']['state'] = 'crashed'

            info.append(pinfo)

        self.reload_states(process_uuids_to_be_force_reloaded)
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
        self.logger.debug('Waiting for process [%s] to run', puuid)
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
        ret = self.processes.get(puuid, False)
        if not ret:
            return ret
        else:
            return ret.is_multiplexer

    def shutdown(self):
        self.logger.info('Shutting down all processes (%s process(es))', len(self.processes.keys()))
        self.shutting_down_phase = True
        for puuid in list(self.processes):
            # self.kill_process(puuid)
            self.stop_process(puuid)

        self._alert_manager.send_alert(
            title='Processes',
            content='Properly closing processes',
            mType='info',
            group=self.projectUUID+'_processesClosing',
            totalCount=len(self.processes.keys())
        )
        for puuid in self.processes.keys():
            subProcObj = self.processes[puuid]._subprocessObj
            try:
                _, _ = subProcObj.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                subProcObj.kill()
                _, _ = subProcObj.communicate()
            except AttributeError as e:
                self.logger.info('Process %s [%s] was recovered from system, skipping communicate', self.processes[puuid].name, puuid)
            self._alert_manager.send_alert(
                title='Processes',
                content='{} closed'.format(self.processes[puuid].name),
                mType='info',
                group=self.projectUUID+'_processesClosing',
                totalCount=1
            )
        self.shutting_down_phase = False

    def reload_states(self, process_uuids):
        if self.shutting_down_phase:
            self.logger.info('Will not restart process as a shutdown has been requested')
            return

        for puuid in process_uuids:
            if puuid not in self.processes:
                self.logger.info('Process [%s] not known by the manager', puuid)
                return

            self.logger.info('Sending reload state command to "%s" [%s]', self.processes[puuid].name, puuid)
            sucess = self.send_command(puuid, 'reload')
            if not sucess:
            # if not sucess and self.boostraping:
                self.logger.info('reload failure, restarting process "%s" [%s]', self.processes[puuid].name, puuid)
                self.restart_process(puuid)

    def pause_process(self, puuid):
        if self.process_started_and_managed(puuid):
            self.logger.info('Pausing process "%s" [%s]', self.processes[puuid].name, puuid)
            self.send_command(puuid, 'pause')
        else:
            pass

    def play_process(self, puuid, data=None):
        if self.process_started_and_managed(puuid):
            self.logger.info('Playing process "%s" [%s]', self.processes[puuid].name, puuid)
            self.send_command(puuid, 'play')
        else: # process not started, starting it
            self.create_process(data, puuid)

    def stop_process(self, puuid):
        if self.process_started_and_managed(puuid):
            self.logger.info('Stopping process "%s" [%s]', self.processes[puuid].name, puuid)
            self.kill_process(puuid)
            self.clean_up_process(puuid)
        else:
            pass

    def restart_process(self, puuid, procData=None, bufsData=None):
        # if puuid in self.processes:
        if self.process_started_and_managed(puuid):
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
        else: # process was not started
            self.logger.info('Wanted to restart process [%s] but it has not been started. Starting it.', puuid)
            self.create_process(procData, puuid)
            # register buffers
            for buuid, bufData in bufsData.items():
                # delete any state before starting
                self._buffer_metadata_interface.clear_info(buuid)
                buffer_config = Link_representation(bufData)
                self.buffers[buuid] = buffer_config
                self.buffers_uuid.add(buuid)


    def send_command(self, puuid, command, data=None):
        self.logger.info('Sending command (%s) to process "%s" [%s]', command, self.processes[puuid].name, puuid)
        jCommand = {}
        jCommand['operation'] = command
        jCommand['data'] = data
        keyCommands = 'command_'+puuid
        process_config = self.processes[puuid]
        self._serv.set('config_'+puuid, process_config.toJSON())
        self._serv.lpush(keyCommands, json.dumps(jCommand))

        # send signal to the module
        self.logger.debug('Sending signal to %s [%s]', self.processes[puuid].name, puuid)
        try:
            self.processes[puuid]._subprocessObj.send_signal(signal.SIGUSR1)
            return True
        except psutil._exceptions.NoSuchProcess as e:
            self.logger.debug('Trying to reload a non-existing process "%s" [%s]: %s', self.processes[puuid].name, puuid, str(e))
            return False


    def should_send_signal(self, process_type):
        MODULE_WITH_SIGNAL = self.config.processes.should_received_a_signal_on_updates
        if process_type in MODULE_WITH_SIGNAL:
            return True

    def kill_process(self, puuid):
        subProcObj = self.processes[puuid]._subprocessObj
        self.logger.info('Killing process "%s" [%s, pid=%s]', self.processes[puuid].name, puuid, subProcObj.pid)
        try:
            subProcObj.terminate()
        except psutil._exceptions.NoSuchProcess as e:
            self.logger.debug('Trying to kill a non-existing process "%s" [%s]: %s', self.processes[puuid].name, puuid, str(e))
        self._serv.delete(puuid)

        try:
            self.logger.info('Waiting for process "%s" to terminate', self.processes[puuid].name)
            _, _ = subProcObj.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            subProcObj.kill()
            _, _ = subProcObj.communicate()
        except AttributeError as e:
            self.logger.info('Process %s [%s] was recovered from system, skipping communicate', self.processes[puuid].name, puuid)

        # delete pending commands
        keyCommands = 'command_'+puuid
        self._serv.delete(keyCommands)

    def create_process(self, data, puuid=None):
        # delete any state before starting
        self._metadata_interface.clear_info(puuid)

        if puuid is None:
            puuid = data.get('puuid', None)
            if puuid is None:
                # gen process UUID
                puuid = 'process_'+genUUID()
        data['puuid'] = puuid
        data['projectUUID'] = self.projectUUID

        if self.process_started_and_managed(puuid):
            self.logger.info('Process "%s" [%s] is started and managed', data.get('name', None), puuid)
            return ""

        pStarted, pid = self.process_started_in_system(puuid, killIt=False)
        # pStarted, pid = self.process_started_in_system(puuid, killIt=True)
        if pStarted:
            self.logger.info('Process "%s" [%s, pid=%s] was already started', data.get('name', None), puuid, pid)
            self._alert_manager.send_alert(title='Process',
                content='{} was started in system (pid={}). Trying to recover state...'.format(data.get('name', None), pid),
                mType='warning', group='singleton')
            # Add process info
            process_config = Process_representation(data)
            process_config.add_subprocessObj(psutil.Process(pid))
            self.processes[puuid] = process_config
            self.processes_uuid.add(puuid)
            if self.should_send_signal(process_config.type):
                self.processes_uuid_with_signal.add(puuid)
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

            # args = shlex.split('screen -S "easyFlow_processes" -X screen -t "{process_type}" bash -c "{virt}; {python_bin} {path} {puuid}; read x;"'.format(
            #         virt='. /home/sami/git/easyFlow/FLOWENV/bin/activate',
            #         path=os.path.join(os.environ['FLOW_PROC'], process_type+'.py'),
            #         process_type=process_type,
            #         puuid=puuid,
            #         python_bin='python3.5')
            # )

            # args = shlex.split('python3.5 -m cProfile -o /home/sami/Desktop/reports/{}.report {} {}'.format(process_type, os.path.join(os.environ['FLOW_PROC'], process_type+'.py'), puuid))
            # cmd: pstats.Stats('remote_input.report').strip_dirs().sort_stats('cumtime').reverse_order().print_stats()
            # args = shlex.split('python3.5 -m memory_profiler {} {}'.format(os.path.join(os.environ['FLOW_PROC'], process_type+'.py'), puuid))
            proc = psutil.Popen(args)
            self.logger.info('Creating new process "%s" [pid=%s] ', data.get('name', 'NO_NAME'), proc.pid)
            # wait that process start the run() phase, publish info
            # self.wait_for_process_running_state(puuid)

            process_config.add_subprocessObj(proc)
            self.processes[puuid] = process_config
            self.processes_uuid.add(puuid)
            if self.should_send_signal(process_type):
                self.processes_uuid_with_signal.add(puuid)
            return process_config

    def delete_process(self, puuid):
        if puuid not in self.processes:
            return
        self.logger.info('Deleting process %s [%s]', self.processes[puuid].name, puuid)
        self.kill_process(puuid)
        # delete residual keys in redis
        keys = self._serv.keys('*{}*'.format(puuid))
        for k in keys:
            self._serv.delete(k)
        # also remove links
        buuids = self.get_connected_buffers(puuid)
        for buuid in buuids:
            self.delete_link(buuid)
        self.clean_up_process(puuid)

    def clean_up_process(self, puuid):
        self.processes_uuid.remove(puuid)
        try:
            self.processes_uuid_with_signal.remove(puuid)
        except ValueError as e:
            pass
        except KeyError as e:
            pass
        del self.processes[puuid]

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
        self.buffers_uuid.add(buuid)
        return buffer_config

    def update_link(self, data):
        buuid = data.get('buuid', None)
        self.logger.info('Updating buffer: "%s"', data.get('name', 'unamed'))
        # gen config
        prev_conf = self.buffers[buuid]
        # merge and overwrite config
        for k, v in data.items():
            setattr(prev_conf, k, v)

        buffer_config = Link_representation(prev_conf.get_dico())
        self._serv.set('config_'+buuid, buffer_config.toJSON())

        # add it to self.buffers
        self.buffers[buuid] = buffer_config
        return buffer_config

    def delete_link(self, buuid):
        if buuid in self.buffers:
            self.logger.info('Deleting buffer %s [%s]', self.buffers[buuid].name, buuid)
            self.buffers_uuid.remove(buuid)
            del self.buffers[buuid]
        else:
            self.logger.info('Deleting buffer [%s]', buuid)

        # delete residual keys in redis
        keys = self._serv.keys('*{}*'.format(buuid))
        for k in keys:
            self._serv.delete(k)
        keys = self._serv_buffers.keys('*{}*'.format(buuid))
        for k in keys:
            self._serv_buffers.delete(k)

    def empty_buffer(self, buuid):
        self.logger.info('Emptying buffer %s', self.buffers[buuid].name)
        self._serv_buffers.delete(buuid)
