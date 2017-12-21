#!/usr/bin/env python3.5
from os import listdir
from os.path import isfile, join
import json

class Project:
    def __init__(self, projectFilename):
        self._project_directory = 'projects/'
        self.projectFilename = projectFilename
        with open(join(self._project_directory, self.projectFilename), 'r') as f:
            jProject = json.load(f)
            self.projectName = jProject['projectName']
            self.projectFilename = self.projectFilename
            self.creationDate = jProject['creationDate']
            self.processNum = jProject['processNum']
            self.processes = jProject['processes']

    def get_project_summary(self):
        p = {}
        p['projectName'] = self.projectName
        p['projectFilename'] = self.projectFilename
        p['creationDate'] = self.creationDate
        p['processNum'] = self.processNum
        return p

    def get_whole_project(self):
        p = {}
        for attr, value in self.__dict__.items():
            if attr.startswith('_'):
                continue
            p[attr] = value
        return p

class Flow_project_manager:
    def __init__(self):
        self.project_directory = 'projects/'

    def get_project_list(self):
        files = [f for f in listdir(self.project_directory) if isfile(join(self.project_directory, f))]
        # get only json files
        projects = [f for f in files if f.endswith('.json')]
        ret = []
        for projectFilename in projects:
            p = Project(projectFilename)
            ret.append(p.get_project_summary())
        return ret

    def get_project(self, projectFilename):
        if projectFilename is None:
            return {}
        else:
            p = Project(projectFilename)
            return p.get_whole_project()
