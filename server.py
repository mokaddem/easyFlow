#!/usr/bin/env python3.5
from flask import Flask, render_template, request, Response, jsonify
import json
import random, math
import configparser
from time import sleep, strftime
import datetime
import os

app = Flask(__name__)

@app.route("/")
def index():
    with open('static/css/img/module_template.svg', 'r') as f:
        raw_svg = f.read()
    raw_svg = "".join(raw_svg.splitlines())

    return render_template('index.html',
                raw_svg=raw_svg,
            )

if __name__ == '__main__':
    app.run(host='localhost', port=9090,  threaded=True)
