#!/usr/bin/env python3.5
from os import listdir, remove
from os.path import isfile, join
import json
import time

class Project:
    def __init__(self, projectFilename, projectName=None):
        self._project_directory = 'projects/'

        if projectFilename is None: # create a new project
            self.projectName = projectName
            self.projectFilename = Project.generateFilenameBaseOnProjectname(projectName)
            self._projectPath = join(self._project_directory, self.projectFilename)
            self.creationTimestamp = int(time.time())
            self.processNum = 0
            self.processes = {}
            self.save_project()
        else:
            self.projectFilename = projectFilename
            self._projectPath = join(self._project_directory, self.projectFilename)
            with open(self._projectPath, 'r') as f:
                jProject = json.load(f)
                self.projectName = jProject['projectName']
                self.projectFilename = self.projectFilename
                self.creationTimestamp = jProject['creationTimestamp']
                self.processNum = jProject['processNum']
                self.processes = jProject['processes']
            # put current project configuration into flow_realtime_db

    def get_project_summary(self):
        p = {}
        p['projectName'] = self.projectName
        p['projectFilename'] = self.projectFilename
        p['creationTimestamp'] = self.creationTimestamp
        p['processNum'] = self.processNum
        return p

    def get_whole_project(self):
        p = {}
        for attr, value in self.__dict__.items():
            if attr.startswith('_'):
                continue
            p[attr] = value
        return p

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
        filename = projectName.replace(' ', '_') + '.json'
        return filename

class Flow_project_manager:
    def __init__(self):
        self.project_directory = 'projects/'

    def get_project_list(self):
        files = [f for f in listdir(self.project_directory) if isfile(join(self.project_directory, f))]
        # get only json files
        projects = [f for f in files if f.endswith('.json')]
        ret = []
        for projectFilename in projects:
            try:
                p = Project(projectFilename)
                ret.append(p.get_project_summary())
            except json.decoder.JSONDecodeError as e:
                pass # invalid file
        return ret

    def get_project(self, projectFilename):
        if projectFilename is None:
            return {}
        else:
            p = Project(projectFilename)
            return p.get_whole_project()

    def applyOperation(self, data, operation):
        if data is None or operation is None:
            return [False, "No data or operation not supplied"]

        if operation == 'create':
            p = Project(None, projectName=data['projectName'])
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
