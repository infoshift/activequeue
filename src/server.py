#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set ft=python:

from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify
from gevent import wsgi
import json
import redis
import os


app = Flask(__name__)
r = redis.Redis(
    host=os.environ.get('REDIS_HOST', '127.0.0.1'),
    port=int(os.environ.get('REDIS_PORT', 6379))
)


@app.route('/queues/<path:queue>', methods=['GET'])
def api_queue_pop(queue):
    queue , data = r.brpop(queue)
    data = json.loads(data)
    return jsonify(data)


@app.route('/queues/<path:queue>', methods=['POST'])
def api_queue_push(queue):
    r.lpush(queue, json.dumps(request.json))
    return jsonify(request.json)


if __name__ == '__main__':
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    wsgi.WSGIServer((HOST, PORT), app.wsgi_app).serve_forever()
