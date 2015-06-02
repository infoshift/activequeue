#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set ft=python:

from gevent import monkey
monkey.patch_all()

import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, request, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from gevent import wsgi
import json
import redis
import os
import uuid
import config


class QueueAdapter(object):

    def push(self, queue, data):
        pass

    def pop(self, queue):
        pass

    def _generate_id(self):
        return uuid.uuid1().hex

    def _loads(self, data):
        """Transforms a valid activequeue payload into a
        python-readable dict."""
        data = json.loads(data)
        return {
            'id': data['id'],
            'data': json.loads(data['data']),
        }

    def _dumps(self, data):
        """Generates an id and creates an activequeue
        payload."""
        d = {
            'id': self._generate_id(),
            'data': json.dumps(data)
        }
        return json.dumps(d)


class RedisAdapter(QueueAdapter):

    def __init__(self, client):
        self.client = client

    def push(self, queue, data):
        d = self._dumps(data)
        a = self.client.lpush(queue, d)
        return json.loads(d)

    def pop(self, queue):
        queue, data = self.client.brpop(queue)
        return self._loads(data)


app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)
r = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
)
r = RedisAdapter(r)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(128), unique=True)
    queue = db.Column(db.String(255))
    status = db.Column(db.String(32), default="PENDING")
    result = db.Column(db.Text, default=None)
    data = db.Column(db.Text, default=None)

    def to_dict(self):
        return {
            'id': self.job_id,
            'queue': self.queue,
            'status': self.status,
            'result': self.result,
            'data': self.data,
        }

    def process(self):
        self.status = "PROCESSING"


@app.route('/queues/<path:queue>', methods=['GET'])
def api_queue_pop(queue):
    data = r.pop(queue)
    job = Job.query.filter_by(job_id=data['id']).first()
    job.process()
    db.session.commit()
    return jsonify(data)


@app.route('/queues/<path:queue>', methods=['POST'])
def api_queue_push(queue):
    data = r.push(queue, request.json)
    job = Job(
        job_id=data['id'],
        queue=queue,
        data=data['data'],
    )
    db.session.add(job)
    db.session.commit()
    return jsonify(data)


@app.route('/jobs/<id>', methods=['POST'])
def api_results_push(id):
    """Stores the result."""
    job = Job.query.filter_by(job_id=id).first_or_404()
    job.status = request.json['status']
    job.result = request.json['result']
    db.session.commit()
    return jsonify(job.to_dict())


@app.route('/jobs/<id>', methods=['GET'])
def api_results_get(id):
    """Retrieves the result."""
    job = Job.query.filter_by(job_id=id).first_or_404()
    return jsonify(job.to_dict())


@app.route('/jobs', methods=['GET'])
def api_jobs():
    return jsonify({
        'jobs': [j.to_dict() for j in Job.query.all()]
    })


if __name__ == '__main__':
    from gevent.wsgi import WSGIServer
    from werkzeug.serving import run_with_reloader

    if config.DEBUG:

        @app.route('/db/rebuild')
        def db_rebuild():
            db.drop_all()
            db.create_all()
            return "Ok"

        from werkzeug.debug import DebuggedApplication
        app = DebuggedApplication(app, evalex=True)

    @run_with_reloader
    def run_server():
        WSGIServer((
            config.HOST,
            config.PORT,
        ), app).serve_forever()
