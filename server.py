#!/usr/bin/env python3.5
from flask import Flask, render_template, request, Response, jsonify
import json
import random, math
import configparser
from time import sleep, strftime
import datetime
import os

app = Flask(__name__)

def read_module_svg_template(filename):
    with open('static/css/img/{}.svg'.format(filename), 'r') as f:
        raw_svg = f.read()
    raw_svg = raw_svg.replace("-inkscape-font-specification:'sans-serif Bold'", '') #removed bad options
    raw_svg = "".join(raw_svg.splitlines())
    return raw_svg

@app.route("/")
def index():
    raw_module_svg = read_module_svg_template('module_templatev3')
    raw_buffer_svg = read_module_svg_template('buffer_template')

    return render_template('index.html',
                raw_module_svg=raw_module_svg,
                raw_buffer_svg=raw_buffer_svg
            )

if __name__ == '__main__':
    app.run(host='localhost', port=9090,  threaded=True)
