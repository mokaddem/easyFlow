#!/usr/bin/env python3.5

from flask import Flask, render_template, request, Response, jsonify
import json
import random, math
import configparser
from time import sleep, strftime
import datetime
import os
import uuid
import flow_project_manager

def genUUID():
    return str(uuid.uuid4())

app = Flask(__name__)
flow_project_manager = flow_project_manager.Flow_project_manager()

def read_module_svg_template(filename):
    with open('static/css/img/{}.svg'.format(filename), 'r') as f:
        raw_svg = f.read()
    raw_svg = raw_svg.replace("-inkscape-font-specification:'sans-serif Bold'", '') #removed bad options
    raw_svg = "".join(raw_svg.splitlines())
    return raw_svg

@app.route("/")
def index():
    raw_module_svg = read_module_svg_template('module_templatev5')
    raw_buffer_svg = read_module_svg_template('buffer_template')

    return render_template('index.html',
                raw_module_svg=raw_module_svg,
                raw_buffer_svg=raw_buffer_svg
            )

@app.route("/save_network", methods=['POST'])
def save_network():
    data = request.get_json()
    return 'OK'

@app.route("/load_network")
def load_network():
    projectName = request.args.get('projectName', None)
    project = flow_project_manager.get_project(projectName)
    return jsonify(project)

@app.route("/get_projects")
def get_projects():
    projects = flow_project_manager.get_project_list()
    return jsonify(projects)

@app.route("/project_operation", methods=['POST'])
def project_operation():
    data = request.get_json()
    operation = data.get('operation', None)
    status = flow_project_manager.applyOperation(data, operation)
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='localhost', port=9090,  threaded=True)
