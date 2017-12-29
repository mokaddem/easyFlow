#!/usr/bin/env python3.5
from os import listdir, remove
from os.path import isfile, join
import json
import time
import re

from util import genUUID, objToDictionnary
# from process import Process
from process_print_to_console import Print_to_console

DEFAULT_TEMP_PROJECT_NAME = 'Temporary project'
DEFAULT_TEMP_PROJECT_INFO = 'To do some tests'

class Project:
    def __init__(self, projectFilename, projectName=DEFAULT_TEMP_PROJECT_NAME, projectInfo=DEFAULT_TEMP_PROJECT_INFO):
        self._project_directory = 'projects/'

        if projectFilename is None: # create a new project
            self.projectName = projectName
            self.projectFilename = Project.generateFilenameBaseOnProjectname(projectName)
            self.projectInfo = projectInfo
            self.isTempProject = True
            self.isTempProjectStr = 'true'
            self._projectPath = join(self._project_directory, self.projectFilename)
            self.creationTimestamp = int(time.time())
            self.processNum = 0
            self.processes = []
            self.save_project()
        else:
            self.projectFilename = projectFilename
            self.isTempProject = False
            self.isTempProjectStr = 'false'
            self._projectPath = join(self._project_directory, self.projectFilename)
            with open(self._projectPath, 'r') as f:
                jProject = json.load(f)
                self.projectName = jProject.get('projectName', 'No project name')
                self.projectInfo = jProject.get('projectInfo', '')
                self.projectFilename = self.projectFilename
                self.creationTimestamp = jProject.get('creationTimestamp', 0)
                self.processNum = jProject.get('processNum', 0)
                self.processes = jProject.get('processes', []) #FIXME Load and start all processes
            # put current project configuration into flow_realtime_db

    def get_project_summary(self):
        p = {}
        p['projectName'] = self.projectName
        p['projectInfo'] = self.projectInfo
        p['projectFilename'] = self.projectFilename
        p['creationTimestamp'] = self.creationTimestamp
        p['processNum'] = self.processNum
        return p

    def get_whole_project(self):
        return objToDictionnary(self)

    def rename_project(self, newName):
        self.projectName = newName
        self.save_project()

    def save_project(self):
        p = {}
        for attr, value in self.__dict__.items():
            if attr.startswith('_'):
                continue
            p[attr] = value
        with open(self._projectPath, 'w') as f:
            json.dump(p, f)

    def delete_project(self):
        remove(self._projectPath)

    def generateFilenameBaseOnProjectname(projectName):
        """
        Normalizes string, converts to lowercase, removes non-alpha characters,
        , converts spaces to underscore and add .json.
        """
        filename = str(projectName).strip().replace(' ', '_')
        filename = re.sub(r'(?u)[^-\w.]', '', filename)
        filename += '.json'
        return filename


    def flowOperation(self, operation, data):
        if operation == 'create_process':
            p = Print_to_console(data)
            self.processes.append(p)
            # response = {'status': 'success'}
            # response['id'] = genUUID()
            # if data.get('x', None) is None or data.get('y', None) is None:
            #     response['x'] = 0; response['y'] = 0
            # else:
            #     response['x'] = data.get('x'); response['y'] = data.get('y')
            # response['name'] = data.get('name', None)
            # response['type'] = data.get('type', None)
            # response['description'] = data.get('description', '')
            # response['bulletin_level'] = data.get('bulletin_level', None)
            response = p.get_representation()
            return response

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
        self.project_directory = 'projects/'
        self.selected_project = None

    def get_project_list(self):
        files = [f for f in listdir(self.project_directory) if isfile(join(self.project_directory, f))]
        # get only json files
        projects = [f for f in files if f.endswith('.json')]
        ret = []
        for projectFilename in projects:
            try:
                p = Project(projectFilename)
                if p.projectName == DEFAULT_TEMP_PROJECT_NAME: # Don't list temp project
                    continue
                ret.append(p.get_project_summary())
            except json.decoder.JSONDecodeError as e:
                pass # invalid file
        return ret

    def select_project(self, projectFilename):
        self.selected_project = Project(projectFilename)
        return self.selected_project.get_whole_project()

    def set_cookies(self, resp, req):
        # project is open and the same in both server-side and client-side
        if self.is_project_open() and self.selected_project.projectFilename == req.cookies.get('projectFilename'):
            return

        if self.is_project_open():
            resp.set_cookie('isTempProject', self.selected_project.isTempProjectStr)
            resp.set_cookie('projectFilename', self.selected_project.projectFilename)
            resp.set_cookie('projectName', self.selected_project.projectName)
        else:
            print('Inconsistency between client-side and server-side')
            resp.set_cookie('isTempProject', 'true')
            resp.set_cookie('projectFilename', DEFAULT_TEMP_PROJECT_NAME)
            resp.set_cookie('projectName', DEFAULT_TEMP_PROJECT_NAME)

    def close_project(self, resp):
        self.selected_project = None
        # set cookies to 'null'
        resp.set_cookie('isTempProject', 'true', expires=0)
        resp.set_cookie('projectFilename', '', expires=0)
        resp.set_cookie('projectName', '', expires=0)

    def is_project_open(self):
        if self.selected_project is None:
            return False
        else:
            return True

    def applyOperation(self, data, operation):
        if data is None or operation is None:
            return [False, "No data or operation not supplied"]

        if operation == 'create':
            p = Project(None, projectName=data['projectName'], projectInfo=data['projectInfo'])
            return [True, "OK"]
        elif operation == 'rename':
            p = Project(data['projectFilename'])
            p.rename_project(data['newProjectName'])
            return [True, "OK"]
        elif operation == 'delete':
            p = Project(data['projectFilename'])
            p.delete_project()
            return [True, "OK"]
        else:
            return [False, "unknown operation"]
