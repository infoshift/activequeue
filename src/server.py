#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set ft=python:

from datetime import datetime
from flask import Flask, request, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
import boto
import config
import json
import redis
import uuid
import gevent
import uuid


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

    def push(self, queue, data, delay=0):
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

    def push(self, queue, data, delay=0):
        d = self._dumps(data)
        queue = self.client.create_queue(self._clean_queue(queue))
        queue.write(queue.new_message(d), delay_seconds=delay)
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

    def __repr__(self):
        return "<Job %s:%s>" % (self.id, self.job_id)

    @classmethod
    def async_push(cls, id, q):
        print "Pushing to queue"
        j = cls.query.filter_by(id=id).first()
        if not j:
            return False

        data = q.push(j.queue, json.loads(j.data))
        j.job_id = data["id"]

        print "Pushed to queue! %s" % j
        return True

    @property
    def is_queued(self):
        return self.job_id is not None

    def push_to_queue(self, q, delay=0):
        data = q.push(self.queue, json.loads(self.data), delay=delay)
        self.job_id = data["id"]

    def set_to_pending(self):
        self.job_id = "pending_%s" % str(uuid.uuid4().hex)

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

    if not data:
        return jsonify({"error": "No message yet."}), 404

    return jsonify(data)


@app.route('/queues/<path:queue>', methods=['POST'])
def api_queue_push(queue):
    now = datetime.utcnow()
    executed_at = request.args.get("executed_at", None)
    push_now = False

    if executed_at:
        executed_at = datetime.strptime(executed_at, "%Y-%m-%dT%H:%M:%S")

    if not executed_at:
        executed_at = datetime.utcnow()
        push_now = True

    diff = int((executed_at - now).total_seconds())

    if diff > 0:
        push_now = False
    else:
        diff = 0

    job = Job(
        queue=queue,
        data=json.dumps(request.json),
        executed_at=executed_at,
    )
    db.session.add(job)
    job.push_to_queue(q, delay=diff)
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
