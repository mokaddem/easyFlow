#!/usr/bin/env python3.5

from flask import Flask, render_template, request, Response, jsonify, flash, redirect, make_response, send_file

from werkzeug.utils import secure_filename

import redis
import zmq
from zmq.log.handlers import PUBHandler

import json
from io import BytesIO
import random, math
import configparser
from time import sleep, strftime, time
import datetime
import os

from util import genUUID, objToDictionnary, Config_parser
from alerts_manager import Alert_manager
from flow_project_manager import ProjectNotFound, Flow_project_manager
easyFlow_conf = os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')
config = Config_parser(easyFlow_conf).get_config()

app = Flask(__name__)
app.config['SECRET_KEY'] = config.server.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.server.upload_folder

flow_project_manager = Flow_project_manager()
try:
    redis_pmanager = redis.Redis(unix_socket_path=config.redis.project.unix_socket_path, decode_responses=True)
except: # fallback using TCP instead of unix_socket
    redis_pmanager = redis.StrictRedis(
        config.redis.project.host,
        config.redis.project.port,
        config.redis.project.db,
        charset="utf-8", decode_responses=True)

context = zmq.Context()

socket_log_zmq = context.socket(zmq.SUB)
socket_log_zmq.bind("tcp://*:{port}".format(port=config.zmq.port))
socket_log_zmq.setsockopt_string(zmq.SUBSCRIBE, '')

alert_manager = Alert_manager()
alert_manager.subscribe()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.server.allowed_file_extension

def read_module_svg_template(filename):
    with open(os.path.join(os.environ['FLOW_STATIC'], 'css/img/{}.svg').format(filename), 'r') as f:
        raw_svg = f.read()
    raw_svg = raw_svg.replace("-inkscape-font-specification:'sans-serif Bold'", '') # removed bad options
    raw_svg = raw_svg.replace("-inkscape-font-specification:'Lato Bold'", '') # removed bad options
    raw_svg = raw_svg.replace("-inkscape-font-specification:'TeX Gyre Cursor Bold'", '') # removed bad options
    raw_svg = "".join(raw_svg.splitlines())
    return raw_svg

@app.route("/")
def index():
    raw_process_svg = read_module_svg_template(config.web.process_svg_template_name)
    raw_multi_in_svg = read_module_svg_template(config.web.mult_input_svg_template_name)
    raw_multi_out_svg = read_module_svg_template(config.web.mult_output_svg_template_name)
    raw_remote_in_svg = read_module_svg_template(config.web.remote_input_svg_template_name)
    raw_remote_out_svg = read_module_svg_template(config.web.remote_output_svg_template_name)
    raw_switch_svg = read_module_svg_template(config.web.switch_svg_template_name)
    raw_buffer_svg = read_module_svg_template(config.web.buffer_svg_template_name)

    all_process_type = Flow_project_manager.list_process_type(config.processes.allowed_script)
    not_displayed_process = [ p.replace('.py', '') for p in config.processes.should_not_be_displayed ]
    all_process_type = [ p for p in all_process_type if p not in not_displayed_process ]

    all_multiplexer_in = Flow_project_manager.list_all_multiplexer_in()
    all_multiplexer_out = Flow_project_manager.list_all_multiplexer_out()
    all_switch = Flow_project_manager.list_all_switch()
    all_process = all_process_type + all_multiplexer_in + all_multiplexer_out + all_switch
    custom_config_json = Flow_project_manager.get_processes_config(all_process)
    all_buffer_type = Flow_project_manager.list_buffer_type(config.buffers.allowed_buffer_type)

    resp = make_response(render_template('index.html',
            raw_process_svg=raw_process_svg,
            raw_multi_in_svg=raw_multi_in_svg,
            raw_multi_out_svg=raw_multi_out_svg,
            raw_remote_in_svg=raw_remote_in_svg,
            raw_remote_out_svg=raw_remote_out_svg,
            raw_switch_svg=raw_switch_svg,
            raw_buffer_svg=raw_buffer_svg,
            all_process_type=all_process_type,
            custom_config_json=custom_config_json,
            auto_refresh_rate=config.web.refresh_metadata_interval_in_sec,
            all_multiplexer_in=all_multiplexer_in,
            all_multiplexer_out=all_multiplexer_out,
            all_switch=all_switch,
            all_buffer_type=all_buffer_type
    ))

    if not flow_project_manager.is_project_open():
        flow_project_manager.reset_cookies(resp)
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
            print('No file part')
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
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
        print('error: no project uuid provided')
        return 'KO'

    JSONProject = flow_project_manager.projectToDico(projectUUID)
    projectName = JSONProject['projectName']
    JSONProject = JSONProject.encode('utf-8')
    resp = make_response(send_file(BytesIO(JSONProject),
             attachment_filename="{}.json".format(projectName),
             as_attachment=True))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    return resp

@app.route("/load_network")
def load_network():
    projectUUID = request.args.get('projectUUID', None) #comes from GET
    projectName = request.cookies.get('projectName', None)
    if projectUUID is None:
        projectUUID = request.cookies.get('projectUUID', None) # check in cookies if not in args

    if projectUUID is None: #FIXME: Throws exception if None or not matching existing project
        raise ProjectNotFound("No project UUID provided")

    if not flow_project_manager.is_project_open():
        project = flow_project_manager.select_project(projectUUID)
    else:
        project = flow_project_manager.selected_project.get_project_summary()
    resp = make_response(jsonify(project))
    flow_project_manager.set_cookies(resp, request)
    return resp

@app.route("/close_project")
def close_project():
    resp = make_response(jsonify({'state': 'closed'}))
    if flow_project_manager.is_project_open():
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

@app.route("/create_process_type" ,methods=['POST'])
def create_process_type():
    data = request.get_json()
    status = flow_project_manager.create_process_type(data)
    return jsonify(status)

@app.route("/flow_operation", methods=['POST'])
def flow_operation():
    data = request.get_json()
    operation = data.get('operation', None)
    status = flow_project_manager.selected_project.flowOperation(operation, data)
    return jsonify(status)

@app.route("/get_log")
def get_log():
    puuid = request.args.get('puuid', None)
    return jsonify(flow_project_manager.selected_project.get_process_logs(puuid))

''' REAL TIME '''

@app.route('/get_pMetadata')
def get_pMetadata():
    if flow_project_manager.is_project_open():
        infos = flow_project_manager.selected_project.get_whole_project()
    else:
        infos = {}
    return jsonify(infos)

@app.route('/get_node_configuration', methods=['POST'])
def get_node_configuration():
    data = request.get_json()
    if flow_project_manager.is_project_open():
        config = flow_project_manager.selected_project.get_configuration(data)
    else:
        config = {}
    return jsonify(config)

@app.route('/get_connected_nodes', methods=['POST'])
def get_connected_nodes():
    data = request.get_json()
    if flow_project_manager.is_project_open():
        connected_bufs = flow_project_manager.selected_project._process_manager.get_connected_buffers(data.get('uuid', ''))
    else:
        connected_bufs = {}
    return jsonify(connected_bufs)

@app.route('/alert_stream')
def alert_stream():
    return Response(alert_manager.make_response_stream(), mimetype="text/event-stream")

@app.route('/log_stream')
def log_stream():
    puuid = request.args.get('puuid', None)
    return Response(make_log_response_stream(puuid), mimetype="text/event-stream")

def make_log_response_stream(puuid):

    while True:
        sleep(0.1)
        # string = socket_log_zmq.recv_string()
        # print(string)
        # topic, logMsg = string.split()
        # print('server_sending', logMsg)
        level, logMsg = socket_log_zmq.recv_multipart()
        level = level.decode('utf8')
        level = level.split('.')[-1]
        logMsg = logMsg.decode('utf8')
        if logMsg.endswith('\n'):
            # trim trailing newline, which will get appended again
            logMsg = logMsg[:-1]
        logDic = {'log_level': level, 'time': int(time()), 'message': logMsg}
        yield 'data: %s\n\n' % json.dumps(logDic)


if __name__ == '__main__':
    # try:
        # app.run(host=config.server.host, port=config.server.port, debug = config.server.debug, threaded=True, use_reloader=False)
    app.run(host=config.server.host, port=config.server.port, debug = config.server.debug, threaded=True, use_reloader=False)
    # except KeyboardInterrupt as e:
    #     print("closing processes")
    #     flow_project_manager.close_project()
