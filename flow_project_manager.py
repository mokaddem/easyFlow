#!/usr/bin/env python3.5
from os import listdir, remove
from os.path import isfile, join
import json
import time
import re
import redis

from util import genUUID, objToDictionnary, dicoToList, Config_parser
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface
from process_manager import Process_manager

class ProjectNotFound(Exception):
    pass

class Project:
    def __init__(self, projectUUID):
            self.config = Config_parser('config/easyFlow_conf.json', projectUUID).get_config()
            try:
                self._serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
            except: # fallback using TCP instead of unix_socket
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

    def setup_project_manager(self):
        self._metadata_interface = Process_metadata_interface()
        self._process_manager = Process_manager(self.projectUUID)
        self._process_manager._alert_manager.send_alert(
            title='System',
            content='Process manager ready',
            mType='success',
            group='singleton',
            totalCount=0
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
        p = self.get_project_summary()
        p['processes'] = self._process_manager.get_processes_info()
        p['buffers'] = self._process_manager.get_buffers_info()
        return p

    def get_configuration(self, data):
        node_type = data.get('type', None)
        if node_type == 'process':
            puuid = data.get('uuid', None)
            return self.processes[puuid]
        elif node_type == 'buffer':
            buuid = data.get('uuid', None)
            return self.buffers[buuid]
        else:
            print('unkown node type')


    def rename_project(self, newName):
        self.projectName = newName
        self.save_project()

    def save_project(self):
        p = self.get_project_summary()
        jProject = json.dumps(p)
        self._serv.set(self.projectUUID, jProject)

    def delete_project(self):
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
        temp = {}
        for buuid, buf in self.buffers.items():
            if (puuid in buf['fromUUID']) or (puuid in buf['toUUID']):
                continue # delete it
            else:
                temp[buuid] = buf
        self.buffers = temp

    def flowOperation(self, operation, data):
        concerned_processes = []
        # print('Flow operation:', operation)
        if operation == 'pause_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.pause_process(puuid)
        elif operation == 'play_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.play_process(puuid)
        elif operation == 'restart_process':
            for puuid in data.get('puuid', []): # may contain multiple processes
                self._process_manager.restart_process(puuid)

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
                if not self._process_manager.is_multiplexer(puuid): # multiplexers do not count as process
                    self.processNum -= 1
                self._process_manager.delete_process(puuid)
                # delete every links of this process
                self.delete_links_of_process(puuid)
                del self.processes[puuid]
        elif operation == 'edit_process':
            ####
            ####    Either save the custom config for the switch here
            ####    or create a new function edit_switch <- prefered
            ####
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
            print(operation)
            print(data)

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

        else:
            return {'status': 'error' }

        self.save_project()
        self._process_manager.reload_states(concerned_processes)
        return {'status': 'success' }

class Flow_project_manager:
    def __init__(self):
        self.selected_project = None
        self.config = Config_parser('config/easyFlow_conf.json').get_config()
        try:
            self.serv = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.serv = redis.StrictRedis(
                self.config.redis.host,
                self.config.redis.port,
                self.config.redis.db,
                charset="utf-8", decode_responses=True)

    @staticmethod
    def list_process_type(allowed_script):
        mypath = './processes/'
        onlyfiles = [f.replace('.py', '') for f in listdir(mypath) if (isfile(join(mypath, f)) and f.endswith('.py') and f in allowed_script)]
        return onlyfiles

    @staticmethod
    def get_processes_config(procs):
        mypath = './processes/'
        to_ret = {}
        for procName in procs:
            with open(join(mypath, procName+'.json')) as f:
                to_ret[procName] = json.load(f)
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
    def list_buffer_type(allowed_buffer_type): # may be usefull later on...
        return allowed_buffer_type

    def get_project_list(self):
        ret = []
        projectUUIDs = self.serv.smembers(self.config.redis.project.redis_key_all_projects)
        projectUUIDs = projectUUIDs if projectUUIDs is not None else []
        for projectUUID in projectUUIDs:
            p = Project(projectUUID)
            ret.append(p.get_project_summary())
        return ret


    def select_project(self, projectUUID):
        if self.is_project_open():
            self.close_project()
        self.selected_project = Project(projectUUID)
        self.config = Config_parser('config/easyFlow_conf.json', projectUUID).get_config()
        self.selected_project.setup_project_manager()
        return self.selected_project.get_project_summary()

    def import_project(self, rawJSONProject):
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

        except json.decoder.JSONDecodeError as e:
            return {'status': False, 'message': 'Project not valid'}

    def projectToDico(self, projectUUID):
        return Project(projectUUID).get_project_summary()

    def set_cookies(self, resp, req):
        # project is open and the same in both server-side and client-side
        if self.is_project_open() and self.selected_project.projectUUID == req.cookies.get('projectUUID'):
            return
        if self.is_project_open():
            resp.set_cookie('projectUUID', self.selected_project.projectUUID)
            resp.set_cookie('projectName', self.selected_project.projectName)

    def reset_cookies(self, resp):
        resp.set_cookie('projectUUID', '', expires=0)
        resp.set_cookie('projectName', '', expires=0)

    def close_project(self, resp=None):
        self.selected_project.close_project()
        self.selected_project = None
        self.config = Config_parser('config/easyFlow_conf.json').get_config()
        if resp is not None:
            self.reset_cookies(resp) # set cookies to 'null'

    def is_project_open(self):
        if self.selected_project is None:
            return False
        else:
            return True

    def applyOperation(self, data, operation):
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
            return [False, "unknown operation"]
