#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set ft=python:

from gevent import monkey
monkey.patch_all()

import pymysql
pymysql.install_as_MySQLdb()

from datetime import datetime
from flask import Flask, request, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
import boto
import config
import json
import redis
import uuid
import gevent


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
        self.client.lpush(queue, d)
        return json.loads(d)

    def pop(self, queue):
        queue, data = self.client.brpop(queue)
        return self._loads(data)

    @classmethod
    def make_queue(cls, redis_host, redis_port):
        r = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
        )
        return cls(r)


class SQSAdapter(QueueAdapter):

    def __init__(self, client):
        self.client = client

    def _clean_queue(self, queue):
        return queue.replace('/', '_')

    def push(self, queue, data):
        d = self._dumps(data)
        queue = self.client.create_queue(self._clean_queue(queue))
        queue.write(queue.new_message(d))
        return json.loads(d)

    def pop(self, queue):
        queue = self.client.create_queue(self._clean_queue(queue))
        messages = queue.get_messages(wait_time_seconds=10)

        if len(messages) == 0:
            return None
        message = messages[0]

        # XXX: Delete message from queue to stop it from recurring.
        queue.delete_message(message)
        return self._loads(message._body)

    @classmethod
    def make_queue(cls, aws_access_key_id, aws_secret_access_key, aws_region):
        conn = boto.connect_sqs()
        return cls(conn)


app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)


q = None

if config.QUEUE_ENGINE == "REDIS":
    q = RedisAdapter.make_queue(config.REDIS_HOST, config.REDIS_PORT)

if config.QUEUE_ENGINE == "SQS":
    q = SQSAdapter.make_queue(
        config.AWS_ACCESS_KEY_ID,
        config.AWS_SECRET_ACCESS_KEY,
        config.AWS_REGION,
    )


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(128), unique=True)
    queue = db.Column(db.String(255))
    status = db.Column(db.String(32), default="PENDING")
    result = db.Column(db.Text, default=None)
    data = db.Column(db.Text, default=None)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def unprocessed(cls):
        """Returns all the unprocessed jobs."""
        r = (
            cls
            .query
            .filter_by(job_id=None)
            .filter(cls.executed_at <= datetime.utcnow())
            .all()
        )
        return r

    @property
    def is_queued(self):
        return self.job_id is not None

    @classmethod
    def push_to_queue(cls, q, id):
        """Pushes a job to the queue."""
        print "acquiring lock..."
        i = cls.query.filter_by(id=id).with_for_update().first()
        print "lock acquired."

        if i.is_queued:
            print "skipping..."
            return

        data = q.push(i.queue, json.loads(i.data))
        i.job_id = data['id']
        db.session.commit()
        db.session.close()
        print "lock released."

    def to_dict(self):
        return {
            'id': self.job_id,
            'queue': self.queue,
            'status': self.status,
            'result': self.result,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'executed_at': self.executed_at.isoformat(),
        }

    def process(self):
        self.status = "PROCESSING"


@app.route('/queues/<path:queue>', methods=['GET'])
def api_queue_pop(queue):
    data = q.pop(queue)
    print data

    if not data:
        return jsonify({"error": "No message yet."}), 404

    #job = Job.query.filter_by(job_id=data['id']).first()
    #if not job:
    #    return jsonify({"error": "No job."}), 404

    return jsonify(data)


@app.route('/queues/<path:queue>', methods=['POST'])
def api_queue_push(queue):
    executed_at = request.args.get("executed_at", datetime.utcnow())
    job = Job(
        queue=queue,
        data=json.dumps(request.json),
        executed_at=executed_at,
    )
    db.session.add(job)
    db.session.commit()
    return jsonify(job.to_dict())


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


def clock():
    while True:
        with app.app_context():
            jobs = Job.unprocessed()

        if len(jobs) > 0:
            print " * %s unprocessed jobs found!" % len(jobs)
            with app.app_context():
                [Job.push_to_queue(q, j.id) for j in jobs]
        gevent.sleep(1)


if __name__ == '__main__':
    from gevent.wsgi import WSGIServer
    from werkzeug.serving import run_with_reloader

    wsgi_app = app

    if config.DEBUG:

        @app.route('/db/rebuild')
        def db_rebuild():
            db.drop_all()
            db.create_all()
            return "Ok"

        from werkzeug.debug import DebuggedApplication
        wsgi_app = DebuggedApplication(wsgi_app, evalex=True)

    @run_with_reloader
    def run_server():
        gevent.joinall([
            gevent.spawn(clock),
            gevent.spawn(WSGIServer((
                config.HOST,
                config.PORT,
            ), wsgi_app).serve_forever)
        ])
