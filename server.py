#!/usr/bin/env python3.5

from flask import Flask, render_template, request, Response, jsonify, flash, redirect, make_response, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

import redis
import json
from io import StringIO
import random, math
import configparser
from time import sleep, strftime
import datetime
import os

from util import genUUID, objToDictionnary
from flow_project_manager import ProjectNotFound, Flow_project_manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
UPLOAD_FOLDER = 'projects/'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# socketio = SocketIO(app)
flow_project_manager = Flow_project_manager()
host='localhost'
port=6780
db=0
redis_pmanager = redis.StrictRedis(host, port, db, charset="utf-8", decode_responses=True)
pmanager_pubsub = redis_pmanager.pubsub()
pmanager_pubsub.subscribe('processes_info')

ALLOWED_EXTENSIONS = set(['json'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    all_process_type = Flow_project_manager.list_process_type()

    resp = make_response(render_template('index.html',
            raw_module_svg=raw_module_svg,
            raw_buffer_svg=raw_buffer_svg,
            all_process_type=all_process_type
    ))

    if not flow_project_manager.is_project_open():
        print('reseting cookies')
        flow_project_manager.reset_cookies(resp, request)
    else: # a project is open
        flow_project_manager.set_cookies(resp, request)
    return resp

@app.route("/save_network", methods=['POST'])
def save_network():
    data = request.get_json()
    return 'OK'

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            print('No file part')
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            print('No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            fileContent = file.read().decode('utf8')
            result = flow_project_manager.import_project(fileContent)
            return jsonify(result)
    return 'KO'

@app.route('/download_file')
def download_file():
    projectUUID = request.args.get('projectUUID', None)
    if projectUUID is None:
        print('error')
        return 'KO'

    strIO = StringIO()
    JSONProject = flow_project_manager.projectToJSON(projectUUID)
    strIO.write(JSONProject)
    strIO.seek(0)
    print('sending')
    return send_file(strIO,
             attachment_filename="testing.txt",
             as_attachment=True)

@app.route("/load_network")
def load_network():
    projectUUID = request.args.get('projectUUID', None) #comes from GET
    projectName = request.cookies.get('projectName', None)
    if projectUUID is None:
        projectUUID = request.cookies.get('projectUUID', None) # check in cookies if not in args

    if projectUUID is None: #FIXME: Throws exception if None or not matching existing project
        raise ProjectNotFound("No project UUID provided")

    project = flow_project_manager.select_project(projectUUID)
    resp = make_response(jsonify(project))
    flow_project_manager.set_cookies(resp, request)
    return resp

@app.route("/close_project")
def close_project():
    resp = make_response(jsonify({'state': 'closed'}))
    flow_project_manager.close_project(resp)
    return resp

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

@app.route("/flow_operation", methods=['POST'])
def flow_operation():
    data = request.get_json()
    operation = data.get('operation', None)
    sleep(0.3)
    status = flow_project_manager.selected_project.flowOperation(operation, data)
    return jsonify(status)

''' SOCKET.IO '''
'''
@socketio.on('updateRequest', namespace='/update')
def test_message(message):
    print(message)
    state = flow_realtime_db.get_state()
    emit('update', {'data': state})
'''

@app.route('/get_pMetadata')
def get_pMetadata():
    infos = flow_project_manager.selected_project._process_manager.get_processes_info()
    return jsonify(infos)

if __name__ == '__main__':
    # socketio.run(app, host='127.0.0.1', port=9090,  debug = True)
    app.run(host='127.0.0.1', port=9090,  debug = True, threaded=True)
