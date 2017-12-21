#!/usr/bin/env python3.5
from flask import Flask, render_template, request, Response, jsonify
import json
import random, math
import configparser
from time import sleep, strftime
import datetime
import os
import uuid

def genUUID():
    return str(uuid.uuid4())

app = Flask(__name__)

def read_module_svg_template(filename):
    with open('static/css/img/{}.svg'.format(filename), 'r') as f:
        raw_svg = f.read()
    raw_svg = raw_svg.replace("-inkscape-font-specification:'sans-serif Bold'", '') #removed bad options
    raw_svg = "".join(raw_svg.splitlines())
    return raw_svg

@app.route("/")
def index():
    raw_module_svg = read_module_svg_template('module_templatev4')
    raw_buffer_svg = read_module_svg_template('buffer_template')

    return render_template('index.html',
                raw_module_svg=raw_module_svg,
                raw_buffer_svg=raw_buffer_svg
            )

@app.route("/save_network", methods=['POST'])
def save_network():
    data = request.get_json()
    print(data)
    return 'OK'

@app.route("/load_network")
def load_network():
    uuid1 = genUUID(); uuid2 = genUUID(); uuid3 = genUUID()
    dummy = {
        'processes':
            [
                {'id': uuid1, 'x': 0, 'y': 0, 'connections': [
                        {'BufferID': genUUID(), 'x': 100, 'y': 100, 'toID': uuid2 },
                        {'BufferID': genUUID(), 'x': -100, 'y': -100, 'toID': uuid3 }
                    ]
                },
                {'id': uuid2, 'x': 200, 'y': 200, 'connections': []},
                {'id': uuid3, 'x': -200, 'y': -200, 'connections': []}
            ]
    }
    return jsonify(dummy)

if __name__ == '__main__':
    app.run(host='localhost', port=9090,  threaded=True)
