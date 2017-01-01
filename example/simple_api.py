#!/usr/bin/env python
import os
import uuid

import boto3
from flask import Flask, jsonify, abort, request, make_response, url_for
from flask_httpauth import HTTPBasicAuth
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BooleanAttribute

app = Flask(__name__)
auth = HTTPBasicAuth()


class Task(Model):
    class Meta:
        table_name = os.environ.get('STAGE', 'dev') + '.tasks'
        region = boto3.Session().region_name
        host = 'http://localhost:8000' \
            if not os.environ.get('LAMBDA_TASK_ROOT') else None
    id = UnicodeAttribute(hash_key=True)
    title = UnicodeAttribute()
    description = UnicodeAttribute()
    done = BooleanAttribute()


@auth.get_password
def get_password(username):
    if username == 'miguel':
        return 'python'
    return None


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)


@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
@app.errorhandler(Model.DoesNotExist)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


def make_public_task(task):
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'done': task.done,
        'uri': url_for('get_task', task_id=task.id)
    }


@app.route('/todo/api/v1.0/tasks', methods=['GET'])
@auth.login_required
def get_tasks():
    return jsonify({'tasks': [make_public_task(task) for task in Task.scan()]})


@app.route('/todo/api/v1.0/tasks/<task_id>', methods=['GET'])
@auth.login_required
def get_task(task_id):
    return jsonify({'task': make_public_task(Task.get(task_id))})


@app.route('/todo/api/v1.0/tasks', methods=['POST'])
@auth.login_required
def create_task():
    data = request.get_json()
    if data is None or 'title' not in data:
        abort(400)
    task = Task(id=uuid.uuid4().hex, title=data['title'],
                description=data.get('description', ''),
                done=data.get('done', False))
    task.save()
    return jsonify({'task': make_public_task(task)}), 201


@app.route('/todo/api/v1.0/tasks/<task_id>', methods=['PUT'])
@auth.login_required
def update_task(task_id):
    task = Task.get(task_id)
    data = request.get_json()
    if not data:
        abort(400)
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'done' in data:
        task.done = True if data['done'] in ['true', 'True', 'yes', 'Yes'] \
            else False
    task.save()
    return jsonify({'task': make_public_task(task)})


@app.route('/todo/api/v1.0/tasks/<task_id>', methods=['DELETE'])
@auth.login_required
def delete_task(task_id):
    task = Task.get(task_id)
    task.delete()
    return jsonify({}), 204


if __name__ == '__main__':
    Task.create_table(read_capacity_units=1, write_capacity_units=1)
    app.run(debug=True)
