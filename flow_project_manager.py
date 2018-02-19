#!/usr/bin/env python3.5
from os import listdir, remove
from os.path import isfile, join
import os
import json
from pprint import pprint
import copy
import time, datetime
import re
import redis
import logging
from psutil import cpu_count, virtual_memory

from util import genUUID, objToDictionnary, dicoToList, datetimeToTimestamp, Config_parser
from bashCommand import BashCommandParser, generate_execute_script_conf
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface
from process_manager import Process_manager
easyFlow_conf = join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')

class ProjectNotFound(Exception):
    pass

class Project:
    def __init__(self, projectUUID):
            self.config = Config_parser(easyFlow_conf, projectUUID).get_config()

            logging.basicConfig(format='%(levelname)s[%(asctime)s]: %(message)s')
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(getattr(logging, self.config.default_project.project_manager.log_level))
            formatter = logging.Formatter('%(levelname)s[%(asctime)s]: %(message)s')
            self.log_handler = logging.FileHandler(join(os.environ['FLOW_LOGS'], 'project.log'))
            self.log_handler.setLevel(getattr(logging, self.config.default_project.project_manager.log_level))
            self.log_handler.setFormatter(formatter)
            self.logger.addHandler(self.log_handler)

            try:
                self._serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
            except: # fallback using TCP instead of unix_socket
                self.logger.warning('Redis unix_socket not used, falling back to TCP')
                self._serv = redis.StrictRedis(
                    self.config.redis.project.host,
                    self.config.redis.project.port,
                    self.config.redis.project.db,
                    charset="utf-8", decode_responses=True)

            # get project from redis
            rawJSONProject = self._serv.get(projectUUID)
            jProject = json.loads(rawJSONProject)
            self.jProject = jProject
            if jProject is None:
                # throws project not found exception
                self.logger.error('Project not found', exc_info=True)
                raise ProjectNotFound("The provided projectUUID does not match any known project")

            self.projectUUID = projectUUID
            self.projectName = jProject.get('projectName', 'No project name')
            self.projectInfo = jProject.get('projectInfo', '')
            self.creationTimestamp = jProject.get('creationTimestamp', 0)
            self.processNum = jProject.get('processNum', 0)

            self._start_command_already_called = False

            self.processes = {}
            for puuid, p in self.jProject.get('processes', {}).items():
                self.processes[puuid] = self.filter_correct_init_fields(p)

            self.buffers = {}
            for buuid, b in self.jProject.get('buffers', {}).items():
                self.buffers[buuid] = b

    def setup_process_manager(self):
        self.logger.info('Setuping process manager')
        self._metadata_interface = Process_metadata_interface()
        self._process_manager = Process_manager(self.projectUUID)
        self._process_manager._alert_manager.send_alert(
            title='System',
            content='Process manager ready'+'''<button id="pcontrol_startAll" type="button" class="btn btn-success" style="display: inline-block; float:right; margin-right: 10px; margin-top: -7px;" onclick="flowControl.startAll();">
                    <span class="glyphicon glyphicon-play-circle"></span> Start all!
                </button>
                ''',
            mType='success',
            group='Process_manager_ready',
            totalCount=1
        )



    # keep fields to be saved in the project
    def filter_correct_init_fields(self, proc):
        init_fields = ['bulletin_level', 'custom_config', 'description', 'name', 'puuid', 'type', 'x', 'y']
        dico = {}
        for k, v in proc.items():
            if k in init_fields:
                dico[k] = v
        return dico

    def get_project_summary(self):
        self.logger.debug('Getting project summary')
        p = {}
        p['projectUUID'] = self.projectUUID
        p['projectName'] = self.projectName
        p['projectInfo'] = self.projectInfo
        p['creationTimestamp'] = self.creationTimestamp
        p['processNum'] = self.processNum
        p['processes'] = self.processes
        p['buffers'] = self.buffers
        return p

    def get_whole_project(self):
        self.logger.debug('Getting whole project')
        p = self.get_project_summary()
        p['processes'] = self._process_manager.get_processes_info()
        p['buffers'] = self._process_manager.get_buffers_info()
        return p

    def get_configuration(self, data):
        self.logger.debug('Getting node configuration')
        node_type = data.get('type', None)
        if node_type == 'process':
            puuid = data.get('uuid', None)
            return self.processes[puuid]
        elif node_type == 'buffer':
            buuid = data.get('uuid', None)
            return self.buffers[buuid]
        else:
            print('unkown node type')

    def get_process_logs(self, puuid):
        logpath = os.path.join(os.environ['FLOW_LOGS'], '{}.log'.format(puuid))
        to_ret = []
        try:
            with open(logpath, 'r') as f:
                log = f.read()
                for l in log.splitlines():
                    metadata, message  = l.split(': ', 1)
                    logLevel, the_time = metadata[:-2].split('[', 1)
                    the_time = datetimeToTimestamp(datetime.datetime.strptime(the_time, "%Y-%m-%d %H:%M:%S,%f"))
                    to_ret.append({'time': the_time, 'log_level': logLevel, 'message': message})
                return to_ret
        except IOError as e:
            self.logger.warning('File not found: Log file %s does not exists', logpath)


    def rename_project(self, newName):
        self.logger.info('Renaming project')
        self.projectName = newName
        self.save_project()

    def save_project(self):
        self.logger.info('Saving project')
        p = self.get_project_summary()
        jProject = json.dumps(p)
        self._serv.set(self.projectUUID, jProject)

    def delete_project(self):
        self.logger.info('Deleting project')
        # delete processes and buffers info in redis
        for puuid in self.processes.keys():
            keys = self._serv.keys('*{}*'.format(puuid))
            for k in keys:
                self._serv.delete(k)
        for buuid in self.buffers.keys():
            keys = self._serv.keys('*{}*'.format(buuid))
            for k in keys:
                self._serv.delete(k)
        # delete project info in redis
        self._serv.delete(self.projectUUID)
        self._serv.srem(self.config.redis.project.redis_key_all_projects, self.projectUUID)

    def close_project(self):
        self.logger.info('Closing project')
        self._process_manager._alert_manager.send_alert(
            title='Processes',
            content='Shutting down processes',
            mType='warning',
            group='singleton',
            totalCount=0
        )
        self._process_manager.shutdown()

    @staticmethod
    def create_new_project(projectName, projectInfo=''):
        p = {}
        p['projectName'] = projectName
        p['projectInfo'] = projectInfo
        p['creationTimestamp'] = int(time.time())
        p['processNum'] = 0
        jProject = json.dumps(p)
        return jProject

    def delete_links_of_process(self, puuid):
        self.logger.info('Deleting links of process %s', puuid)
        temp = {}
        for buuid, buf in self.buffers.items():
            if (puuid in buf['fromUUID']) or (puuid in buf['toUUID']):
                continue # delete it
            else:
                temp[buuid] = buf
        self.buffers = temp

    def get_connected_buffers(self, puuid):
        self.logger.debug('Getting connected buffers of process "%s" [%s]', self.processes[puuid]['name'], puuid)
        buuids = []
        for buuid, buf in self.buffers.items():
            if (puuid in buf['fromUUID']) or (puuid in buf['toUUID']):
                buuids.append(buuid)
        return buuids

    def flowOperation(self, operation, data):
        self.logger.info('Executing operation %s', operation)
        concerned_processes = []
        # print('Flow operation:', operation)
        if operation == 'pause_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.pause_process(puuid)
        elif operation == 'play_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.play_process(puuid, data=self.processes[puuid])
        elif operation == 'stop_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.stop_process(puuid)
        elif operation == 'restart_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                buuids = self.get_connected_buffers(puuid)
                bufs_info = {}
                for buuid in buuids:
                    bufs_info[buuid] = self.buffers[buuid]
                self._process_manager.restart_process(puuid, self.processes[puuid], bufs_info)
        elif operation == 'log_to_zmq':
            puuid = data.get('puuid', None)
            self._process_manager.send_command(puuid, 'log_to_zmq')
        elif operation == 'stop_log_to_zmq':
            puuid = data.get('puuid', None)
            self._process_manager.send_command(puuid, 'stop_log_to_zmq')

        # ''' PROCESSES '''
        elif operation == 'create_process':
            process_config = self._process_manager.create_process(data)
            puuid = process_config.puuid
            if puuid == 0:
                return {'status': 'error'}
            self.processes[puuid] = self.filter_correct_init_fields(process_config.get_dico())
            self.processNum += 1
        elif operation == 'delete_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.delete_process(puuid)
                # delete every links of this process
                self.delete_links_of_process(puuid)
                del self.processes[puuid]
                if not self._process_manager.is_multiplexer(puuid): # multiplexers do not count as process
                    self.processNum -= 1
        elif operation == 'edit_process':
            process_config = self._process_manager.update_process(data)
            puuid = process_config.puuid
            self.processes[puuid] = self.filter_correct_init_fields(process_config.get_dico())
            concerned_processes = [puuid]

        # ''' LINKS '''
        elif operation == 'add_link':
            link_config = self._process_manager.create_link(data)
            buuid = link_config.buuid
            if buuid == 0:
                return {'status': 'error'}
            self.buffers[buuid] = link_config.get_dico()
            concerned_processes = [link_config.fromUUID, link_config.toUUID]
        elif operation == 'delete_link':
            for buuid in data.get('buuid', []):
                self._process_manager.delete_link(buuid)
                link_config = self.buffers[buuid] # get old processes
                concerned_processes = [link_config['fromUUID'], link_config['toUUID']]
                del self.buffers[buuid] # effectively delete
        elif operation == 'edit_link':
            link_config = self._process_manager.update_link(data)
            buuid = link_config.buuid
            self.buffers[buuid] = link_config.get_dico()
            concerned_processes = [link_config.fromUUID, link_config.toUUID]
        elif operation == 'empty_buffer':
            for buuid in data.get('buuid', []): # may contain multiple processes
                self._process_manager.empty_buffer(buuid)

        # ''' MULT_INPUT '''
        elif operation == 'create_mult_input':
            mult_input_config = self._process_manager.create_process(data)
            puuid = mult_input_config.puuid
            if puuid == 0:
                return {'status': 'error'}
            self.processes[puuid] = self.filter_correct_init_fields(mult_input_config.get_dico())

        # ''' MULT_OUTPUT '''
        elif operation == 'create_mult_output':
            mult_output_config = self._process_manager.create_process(data)
            puuid = mult_output_config.puuid
            if puuid == 0:
                return {'status': 'error'}
            self.processes[puuid] = self.filter_correct_init_fields(mult_output_config.get_dico())

        # ''' SWITCH '''
        elif operation == 'create_switch':
            switch_config = self._process_manager.create_process(data)
            puuid = switch_config.puuid
            if puuid == 0:
                return {'status': 'error'}
            self.processes[puuid] = self.filter_correct_init_fields(switch_config.get_dico())

        # ''' DRAGGING '''
        elif operation == 'node_drag':
            if data['nodeType'] == 'process':
                x = data['x']
                y = data['y']
                puuid = data['uuid']
                self.processes[puuid]['x'] = x
                self.processes[puuid]['y'] = y
                # self.save_project()
            elif data['nodeType'] == 'buffer':
                x = data['x']
                y = data['y']
                buuid = data['uuid']
                self.buffers[buuid]['x'] = x
                self.buffers[buuid]['y'] = y

        # ''' OTHERS '''
        elif operation == 'start_all':
            if self._start_command_already_called: # prevent multiple execution
                return {'status': 'sucess' }
            self._process_manager.start_processes(self.processes, self.buffers)
            self._start_command_already_called = True
            return {'status': 'sucess' }

        elif operation == 'clone':
            uuid_mapping = {}
            uuid_buffers = []
            uuids = data['uuids']
            self.logger.info('Cloning %s nodes', len(uuids))
            for uuid in uuids:
                if uuid.startswith('process_'):
                    node_conf = copy.deepcopy(self.processes[uuid])
                    del node_conf['puuid']
                    new_puuid = 'process_' + genUUID()
                    node_conf['puuid'] = new_puuid
                    uuid_mapping[uuid] = new_puuid # register the mapping
                    self.processes[new_puuid] = self.filter_correct_init_fields(node_conf)
                    self.processNum += 1
                    import pprint
                    pprint.pprint(node_conf)

                elif uuid.startswith('buffer_'): # save buffers uuid so that the mapping complete
                    uuid_buffers.append(uuid)

                else:
                    return {'status': 'error, unkown uuid prefix'}

            for uuid in uuid_buffers:
                node_conf = copy.deepcopy(self.buffers[uuid])
                del node_conf['buuid']
                # remap uuids
                node_conf['fromUUID'] = uuid_mapping[node_conf['fromUUID']]
                node_conf['toUUID'] = uuid_mapping[node_conf['toUUID']]
                link_config = self._process_manager.create_link(node_conf) # save buffer config in redis

                self.buffers[link_config.buuid] = link_config.get_dico()
                concerned_processes += [link_config.fromUUID, link_config.toUUID]

        elif operation == 'create_from_bash_command':
            NORMAL_PIPE = 'NORMAL'          # |
            MULT_PIPE = 'MULT'              # |{x}
            INDIV_PIPE = 'INDIV'            # *|
            MULT_INDIV_PIPE = 'MULT_INDIV'  # *|{x}

            prev_proc = ['empty_proc']  # previous added processes (empty_proc needed for first iteration)
            cur_proc = []   # currently added processes
            rawBashCommand = data['bashCommand']
            parsed_command = BashCommandParser(rawBashCommand).get()
            print(parsed_command)
            for index_proc_list, arguments in enumerate(parsed_command): # for each level-process
                pipe_num = arguments['options']['pipe_num']
                pipe_type = arguments['options']['pipe_type']
                duplicate = True if pipe_type in [INDIV_PIPE, MULT_INDIV_PIPE] else False

                multiplier = len(prev_proc) if duplicate else 1 # should we clone a process for each newly created process
                for proc_num in range(pipe_num*multiplier): # for each requested process number (level)
                    # create processes
                    process_type, custom_config = generate_execute_script_conf(arguments['procType'], arguments['options']['raw'])
                    conf = {
                        'name': arguments['procType'],
                        'type': process_type,
                        'description': 'Raw arguments: ' + arguments['options']['raw'],
                        'puuid': 'process_' + genUUID(),
                        'projectUUID': self.projectUUID,
                        'custom_config': custom_config
                    }
                    puuid = self.util_create_process(conf)
                    cur_proc.append(puuid)

                # create links
                if pipe_type == NORMAL_PIPE:
                    if index_proc_list == 0: # no link for the first process
                        pass
                    else:
                        mux_uuid = None
                        for old_proc_uuid in prev_proc: # for each previously added proc (level-1)
                            if len(prev_proc) > 1: # need to add a mux_in
                                # create_mux_in once
                                mux_uuid = mux_uuid if mux_uuid is not None else self.util_create_mux(out=False)
                                # link old_proc_uuid to mux_in
                                self.util_create_buffer(old_proc_uuid, mux_uuid)
                                # link mux_out to cur_puuid
                        puuid = cur_proc[0] # only 1 proc in there anyway
                        self.util_create_buffer(mux_uuid, puuid)

                elif pipe_type == MULT_PIPE: # redirect all old to the newly created
                    if index_proc_list == 0: # no link for the first process
                        pass
                    else:
                        for old_proc_uuid in prev_proc: # for each previously added proc (level-1)
                            if len(cur_proc) > 1: # need to add a mux_out
                                # create_mux_out
                                mux_uuid = self.util_create_mux(out=True)
                                # link old_proc_uuid to mux_out
                                self.util_create_buffer(old_proc_uuid, mux_uuid)
                                for puuid in cur_proc:
                                    # link mux_out to cur_puuid
                                    self.util_create_buffer(mux_uuid, puuid)
                            else:
                                #old_proc_uuid -> puuid
                                self.util_create_buffer(old_proc_uuid, cur_proc[0])

                elif pipe_type == INDIV_PIPE: # redirect all old to the newly created
                    if index_proc_list == 0: # no link for the first process
                        pass
                    else:
                        for old_uuid, cur_uuid in zip(prev_proc, cur_proc):
                            # link old_uuid -> cur_uuid
                            self.util_create_buffer(old_uuid, cur_uuid)

                elif pipe_type == MULT_INDIV_PIPE: # redirect all old to the newly created
                    if index_proc_list == 0: # no link for the first process
                        pass
                    else:
                        for index, old_proc_uuid in enumerate(prev_proc): # for each previously added proc (level-1)
                            if len(cur_proc) > 1: # need to add a mux_out
                                # create_mux_out
                                mux_uuid = self.util_create_mux(out=True)
                                # link old_proc_uuid to mux_out
                                self.util_create_buffer(old_proc_uuid, mux_uuid)
                                for puuid in cur_proc[index*pipe_num:index*pipe_num+pipe_num]:
                                    # link mux_out to cur_puuid
                                    self.util_create_buffer(mux_uuid, puuid)
                            else:
                                # link old_proc_uuid -> puuid
                                puuid = cur_proc[index:index+1]
                                self.util_create_buffer(old_proc_uuid, puuid)

                prev_proc = cur_proc
                cur_proc = []


        else:
            self.logger.warning('Unknown operation: %s', operation)
            return {'status': 'error' }

        self.save_project()
        self._process_manager.reload_states(concerned_processes)
        return {'status': 'success' }

    def util_create_buffer(self, fromUUID, toUUID):
        conf = {
            'name': 'buffer',
            'type': 'FIFO',
            'buuid': 'buffer_' + genUUID(),
            'projectUUID': self.projectUUID,
            'fromUUID': fromUUID,
            'toUUID': toUUID
        }
        link_config = self._process_manager.update_link(conf)
        buuid = link_config.buuid
        self.buffers[buuid] = link_config.get_dico()
        return buuid

    def util_create_mux(self, out=True):
        mux_type = 'multiplexer_out' if out else 'multiplexer_in'
        conf = {
            'name': "Mux_out",
            'type': mux_type,
            'description': '',
            'puuid': 'process_' + genUUID(),
            'projectUUID': self.projectUUID,
            'custom_config': {'multiplex_logic': 'Interleave'}
        }
        mult_output_config = self._process_manager.update_process(conf)
        mux_uuid = mult_output_config.puuid
        self.processes[mux_uuid] = self.filter_correct_init_fields(mult_output_config.get_dico())
        return mux_uuid

    def util_create_process(self, conf):
        process_config = self._process_manager.update_process(conf)
        puuid = process_config.puuid
        self.processes[puuid] = self.filter_correct_init_fields(process_config.get_dico())
        self.processNum += 1
        return puuid

class Flow_project_manager:
    def __init__(self):
        self.selected_project = None
        self.config = Config_parser(easyFlow_conf).get_config()

        logging.basicConfig(format='%(levelname)s[%(asctime)s]: %(message)s')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.default_project.project_manager.log_level))
        formatter = logging.Formatter('%(levelname)s[%(asctime)s]: %(message)s')
        self.log_handler = logging.FileHandler(join(os.environ['FLOW_LOGS'], 'project.log'))
        self.log_handler.setLevel(getattr(logging, self.config.default_project.project_manager.log_level))
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

        try:
            self.serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.warning('Redis unix_socket not used, falling back to TCP')
            self.serv = redis.StrictRedis(
                self.config.redis.host,
                self.config.redis.port,
                self.config.redis.db,
                charset="utf-8", decode_responses=True)

    @staticmethod
    # return [scriptname, description, tags]
    def list_process_type(allowed_script):
        mypath = os.environ['FLOW_PROC']
        onlyfiles = [f.replace('.py', '') for f in listdir(mypath) if (isfile(join(mypath, f)) and f.endswith('.py') and f in allowed_script)]
        to_ret = [ [name]+Flow_project_manager.get_script_info(name) for name in onlyfiles ]
        return to_ret

    @staticmethod
    def get_script_info(scriptname):
        mypath = os.environ['FLOW_PROC']
        try:
            with open(join(mypath, scriptname+'.json'), 'r') as f:
                scriptInfo = json.load(f)
                tags = ' '.join(scriptInfo.get('tags', ''))
                return [scriptInfo.get('description', ''), tags]
        except Exception as e:
            return ['', '']

    @staticmethod
    def get_processes_config(procs):
        mypath = os.environ['FLOW_PROC']
        to_ret = {}
        for procName in procs:
            try:
                with open(join(mypath, procName+'.json')) as f:
                    to_ret[procName] = json.load(f)
            except Exception as e:
                print('Error while trying to load %s: %s', join(mypath, procName+'.json'), str(e))
        return to_ret

    @staticmethod
    def list_all_multiplexer_in():
        return ['multiplexer_in']
    @staticmethod
    def list_all_multiplexer_out():
        return ['multiplexer_out']

    @staticmethod
    def list_all_switch():
        return ['switch']

    @staticmethod
    def list_all_remote_in():
        return ['remote_input']
    @staticmethod
    def list_all_remote_out():
        return ['remote_output']

    @staticmethod
    def list_buffer_type(allowed_buffer_type): # may be usefull later on...
        return allowed_buffer_type

    @staticmethod
    def get_max_cpu_load():
        return 100*cpu_count()
    @staticmethod
    def get_max_memory_load():
        return virtual_memory().total

    def get_project_list(self):
        self.logger.info('Getting project list')
        ret = []
        projectUUIDs = self.serv.smembers(self.config.redis.project.redis_key_all_projects)
        projectUUIDs = projectUUIDs if projectUUIDs is not None else []
        for projectUUID in projectUUIDs:
            p = Project(projectUUID)
            ret.append(p.get_project_summary())
        return ret

    def select_project(self, projectUUID):
        self.logger.info('Selected project %s', projectUUID)
        if self.is_project_open():
            self.close_project()
        self.selected_project = Project(projectUUID)
        self.config = Config_parser(easyFlow_conf, projectUUID).get_config()
        self.selected_project.setup_process_manager()
        return self.selected_project.get_project_summary()

    def import_project(self, rawJSONProject):
        self.logger.info('Importing project')
        required_fields = ['projectName', 'projectInfo', 'creationTimestamp', 'processNum', 'processes']
        try:
            jProject = json.loads(rawJSONProject)
            # validate project: all requiered fields are present
            if all([rF in jProject for rF in Project.required_fields]):
                newUUID = genUUID()
                keyP = 'project_{}'.format(newUUID)
                self.serv.set(keyP, json.dumps(jProject))
                self.serv.sadd(self.config.redis.project.redis_key_all_projects, keyP)
                return {'status': True }
            else:
                return {'status': False, 'message': 'Project does not contain all required fields'}

        except:
            return {'status': False, 'message': 'Project not valid'}


    def projectToDico(self, projectUUID):
        return Project(projectUUID).get_project_summary()

    def set_cookies(self, resp, req):
        # project is open and the same in both server-side and client-side
        if self.is_project_open() and self.selected_project.projectUUID == req.cookies.get('projectUUID'):
            return
        if self.is_project_open():
            self.logger.info('Setting cookies')
            resp.set_cookie('projectUUID', self.selected_project.projectUUID)
            resp.set_cookie('projectName', self.selected_project.projectName)

    def reset_cookies(self, resp):
        self.logger.info('Resetting cookies')
        resp.set_cookie('projectUUID', '', expires=0)
        resp.set_cookie('projectName', '', expires=0)

    def close_project(self, resp=None):
        self.logger.info('Closing project')
        self.selected_project.close_project()
        self.selected_project = None
        self.config = Config_parser(easyFlow_conf).get_config()
        if resp is not None:
            self.reset_cookies(resp) # set cookies to 'null'

    def is_project_open(self):
        if self.selected_project is None:
            return False
        else:
            return True

    def create_process_type(self, data):
        mypath = os.environ['FLOW_PROC']
        procName = data.get('name', None)
        procExtendType = 'Process' if data.get('rcv_message', True) else 'Process_no_input'
        if procName is None:
            self.logger.warning('Process type creation failed')
            return {'status': 'failure'}

        pConfig = {}
        for param, j in data.items(): # re-construct config #FIXME should not be done
            if param in ['rcv_message']: # ignore some fields
                continue
            elif param in ['name', 'description']:
                pConfig[param] = j
                continue
            elif param == 'tags':
                pConfig[param] = j.split(',')
                continue

            pConfig[param] = {}
            for k, v in j.items():
                if k == 'additional_options':
                    # pConfig[param][k] = json.loads(v) #FIXME
                    pConfig[param][k] = v
                else:
                    pConfig[param][k] = v

        with open(join(mypath, procName+'.json'), 'w') as f:
            json.dump(pConfig, f)

        with open(join(mypath, 'process_template_to_be_filled'+'.py'), 'r') as f_template:
            content = f_template.read()
            content = content.format(
                parameters=str(pConfig.keys()),
                procExtendType=procExtendType,
                procExtendTypeClass='p'+procExtendType[1:],
                processType=procName)

            with open(join(mypath, procName+'.py'), 'w') as f_proc:
                f_proc.write(content)
            self.logger.info('Written new process type %s', procName)

        return {'status': 'success'}

    def applyOperation(self, data, operation):
        self.logger.info('Applying operation %s', operation)
        if data is None or operation is None:
            return [False, "No data or operation not supplied"]

        if operation == 'create':
            jProject = Project.create_new_project(data['projectName'], projectInfo=data['projectInfo'])
            newUUID = genUUID()
            keyP = 'project_{}'.format(newUUID)
            self.serv.set(keyP, jProject)
            self.serv.sadd(self.config.redis.project.redis_key_all_projects, keyP)
            return [True, "OK"]
        elif operation == 'rename':
            p = Project(data['projectUUID'])
            p.rename_project(data['newProjectName'])
            return [True, "OK"]
        elif operation == 'delete':
            #Close project if already running
            p = Project(data['projectUUID'])
            p.delete_project()
            if self.is_project_open() and data['projectUUID'] == self.selected_project.projectUUID:
                # self.selected_project.close_project()
                self.close_project()
            print('deleted', data['projectUUID'])
            return [True, "OK"]
        else:
            self.logger.warning('Unknown operation: %s', operation)
            return [False, "unknown operation"]
