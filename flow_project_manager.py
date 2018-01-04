#!/usr/bin/env python3.5
from os import listdir, remove
from os.path import isfile, join
import json
import time
import re
import redis

from util import genUUID, objToDictionnary
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface
from process_manager import Process_manager

from process_print_to_console import Print_to_console

DEFAULT_TEMP_PROJECT_UUID = '36bcefc6-4a7d-4605-96f6-94a133d0e82d'
DEFAULT_TEMP_PROJECT_NAME = 'Temporary project'
DEFAULT_TEMP_PROJECT_INFO = 'To do some tests'

host='localhost'
port=6780
db=0
KEYALLPROJECT = 'AllProject'

class ProjectNotFound(Exception):
    pass

class Project:
    required_fields = ['projectName', 'projectInfo', 'creationTimestamp', 'processNum', 'processes']
    def __init__(self, projectUUID, projectName=DEFAULT_TEMP_PROJECT_NAME, projectInfo=DEFAULT_TEMP_PROJECT_INFO):
            # get project from redis
            self._serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
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

            self.processes = []
            for p in self.jProject.get('processes', []):
                self.processes.append(self.filter_correct_init_fields(p))

    def setup_project_manager(self):
        self._metadata_interface = Process_metadata_interface()
        self._process_manager = Process_manager(self.projectUUID, self.processes)

    def filter_correct_init_fields(self, proc):
        init_fields = ['bulletin_level', 'connections', 'description', 'name', 'puuid', 'type', 'x', 'y']
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
        return p

    def get_whole_project(self):
        p = self.get_project_summary()
        p['processes'] = self._process_manager.get_processes_info()
        return p

    def rename_project(self, newName):
        self.projectName = newName
        self.save_project()

    def save_project(self):
        p = self.get_project_summary()
        jProject = json.dumps(p)
        self._serv.set(self.projectUUID, jProject)

    def delete_project(self):
        self._serv.delete(self.projectUUID)
        self._serv.srem(KEYALLPROJECT, self.projectUUID)

    def create_new_project(projectName, projectInfo=''):
        p = {}
        p['projectName'] = projectName
        p['projectInfo'] = projectInfo
        p['creationTimestamp'] = int(time.time())
        p['processNum'] = 0
        jProject = json.dumps(p)
        return jProject

    def flowOperation(self, operation, data):
        if operation == 'create_process':
            process_config = self._process_manager.create_process(data)
            puuid = process_config.puuid
            if puuid == 0:
                return {'status': 'error'}

            self.processes.append(self.filter_correct_init_fields(process_config.get_dico()))
            pinfo = self._metadata_interface.get_info(puuid)
            self.save_project()
            return pinfo

        elif operation == 'add_link':
            response = {'status': 'success'}
            response['id'] = genUUID()
            return response

        elif operation == 'update':
            return {'status': 'error' }
        else:
            return {'status': 'error' }

class Flow_project_manager:
    def __init__(self):
        self.selected_project = None
        self.serv = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)

    def list_process_type():
        mypath = './processes/'
        ALLOWED_PROCESS_TYPE = set(['print_to_console.py', 'print_current_time.py'])
        onlyfiles = [f.replace('.py', '') for f in listdir(mypath) if (isfile(join(mypath, f)) and f.endswith('.py') and f in ALLOWED_PROCESS_TYPE)]
        return onlyfiles

    def get_project_list(self):
        ret = []
        projectUUIDs = self.serv.smembers(KEYALLPROJECT)
        projectUUIDs = projectUUIDs if projectUUIDs is not None else []
        for projectUUID in projectUUIDs:
            p = Project(projectUUID)
            ret.append(p.get_project_summary())
        return ret


    def select_project(self, projectUUID):
        print('selecting', projectUUID)
        self.selected_project = Project(projectUUID)
        self.selected_project.setup_project_manager()
        return self.selected_project.get_project_summary()

    def import_project(self, rawJSONProject):
        try:
            jProject = json.loads(rawJSONProject)
            # validate project: all requiered fields are present
            if all([rF in jProject for rF in Project.required_fields]):
                newUUID = genUUID()
                keyP = 'project_{}'.format(newUUID)
                self.serv.set(keyP, json.dumps(jProject))
                self.serv.sadd(KEYALLPROJECT, keyP)
                return {'status': True }
            else:
                return {'status': False, 'message': 'Project does not contain all required fields'}

        except json.decoder.JSONDecodeError as e:
            return {'status': False, 'message': 'Project not valid'}

    def projectToJSON(self, projectUUID):
        return json.dumps(Project(projectUUID).get_whole_project())

    def set_cookies(self, resp, req):
        # project is open and the same in both server-side and client-side
        if self.is_project_open() and self.selected_project.projectUUID == req.cookies.get('projectUUID'):
            return
        if self.is_project_open():
            resp.set_cookie('projectUUID', self.selected_project.projectUUID)
            resp.set_cookie('projectName', self.selected_project.projectName)

    def reset_cookies(self, resp, req):
        resp.set_cookie('projectUUID', '', expires=0)
        resp.set_cookie('projectName', '', expires=0)

    def close_project(self, resp):
        self.selected_project = None
        self.reset_cookies # set cookies to 'null'

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
            self.serv.sadd(KEYALLPROJECT, keyP)
            return [True, "OK"]
        elif operation == 'rename':
            p = Project(data['projectUUID'])
            p.rename_project(data['newProjectName'])
            return [True, "OK"]
        elif operation == 'delete':
            p = Project(data['projectUUID'])
            p.delete_project()
            return [True, "OK"]
        else:
            return [False, "unknown operation"]
