from __future__ import absolute_import

from datetime import datetime
import os
import string
import random
import sys

import boto3
import botocore
import climax
from lambda_uploader.package import build_package


@climax.group()
def main():
    pass


@main.command()
@climax.argument('--name',
                 help='API name. A random name is used if this is not given.')
@climax.argument('--description', default='Deployed with slam.',
                 help='Description of the API.')
@climax.argument('--base_path', default='api', help='Base path for the API.')
@climax.argument('--timeout', type=int, default=5,
                 help='The timeout for the lambda function in seconds.')
@climax.argument('--memory', type=int, default=128,
                 help=('The memory allocation for the lambda function in '
                       'megabytes.'))
@climax.argument('--requirements', default='requirements.txt',
                 help='The location of the project\'s requirements file.')
@climax.argument('wsgi_app',
                 help='The WSGI app instance, in the format module:app.')
def init(name, description, base_path, timeout, memory, requirements,
         wsgi_app):
    """Generate handler.py file with configuration."""
    handler = """import os

config = {{
    'name': '{name}',
    'description': '{description}',
    'base_path': '{base_path}',
    'timeout': {timeout},
    'memory': {memory},
    'requirements': '{requirements}',
}}

if os.environ.get('LAMBDA_TASK_ROOT'):
    from slam import lambda_handler
    from {module} import {app}
    lambda_handler.app = {app}
"""
    module, app = wsgi_app.split(':')
    if not name:
        name = module
    name += '-' + ''.join(random.choice(
            string.ascii_lowercase + string.digits) for _ in range(6))
    if os.path.exists('handler.py'):
        print('handler.py file exists! Please delete old version if you want '
              'to regenerate it.')
        sys.exit(1)
    with open('handler.py', 'wt') as f:
        f.write(handler.format(module=module, app=app, name=name,
                               description=description.replace("'", "\'"),
                               base_path=base_path, timeout=timeout,
                               memory=memory, requirements=requirements))
    print('A handler.py for your lambda server has been generated. Please '
          'add it to source control.')


def _load_config():
    saved_sys_path = sys.path
    sys.path = [os.getcwd()]
    from handler import config
    sys.path = saved_sys_path
    return config


def _build(config):
    pkg_name = datetime.utcnow().strftime("lambda_package.%Y%m%d_%H%M%S.zip")
    ignore = ['\\.pyc$']
    if os.environ.get('VIRTUAL_ENV'):
        # make sure the currently active virtualenv is not included in the pkg
        venv = os.path.relpath(os.environ['VIRTUAL_ENV'], os.getcwd())
        if not venv.startswith('.'):
            ignore.append(venv.replace('/', '\/') + '\/.*$')
    build_package('.', config['requirements'], ignore=ignore,
                  zipfile_name=pkg_name)
    return pkg_name


@main.command()
def build():
    """Build lambda package."""
    config = _load_config()

    print("Building lambda package...")
    pkg_name = _build(config)
    print("{} has been built successfully.".format(pkg_name))


@main.command()
@climax.argument('--template', help='Custom cloudformation template to '
                 'deploy.')
def deploy(template):
    """Deploy API to AWS."""
    config = _load_config()

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')
    region = boto3.session.Session().region_name

    print("Building lambda package...")
    pkg_name = _build(config)

    # determine if this is a new deployment or an update
    previous_deployment = None
    try:
        previous_deployment = cfn.describe_stacks(
            StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        pass
    if previous_deployment:
        for p in previous_deployment['Parameters']:
            if p['ParameterKey'] == 'LambdaS3Bucket':
                bucket = p['ParameterValue']
                break
    else:
        bucket = config['name']
        try:
            s3.head_bucket(Bucket=bucket)
        except botocore.exceptions.ClientError:
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={
                'LocationConstraint': region})

    # upload pkg to s3
    s3.upload_file(pkg_name, bucket, pkg_name)
    os.remove(pkg_name)

    template = template or os.path.join(os.path.dirname(__file__), 'cfn.yaml')
    with open(template) as f:
        template_body = f.read()

    if previous_deployment is None:
        print("Deploying API...")
        cfn.create_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=[
                             {'ParameterKey': 'LambdaS3Bucket',
                              'ParameterValue': bucket},
                             {'ParameterKey': 'LambdaS3Key',
                              'ParameterValue': pkg_name},
                             {'ParameterKey': 'LambdaTimeout',
                              'ParameterValue': str(config['timeout'])},
                             {'ParameterKey': 'LambdaMemorySize',
                              'ParameterValue': str(config['memory'])},
                             {'ParameterKey': 'APIName',
                              'ParameterValue': config['name']},
                             {'ParameterKey': 'APIDescription',
                              'ParameterValue': config['description']},
                             {'ParameterKey': 'APIBasePath',
                              'ParameterValue': config['base_path']}],
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_create_complete')
    else:
        print("Updating API...")
        cfn.update_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=[
                             {'ParameterKey': 'LambdaS3Bucket',
                              'ParameterValue': bucket},
                             {'ParameterKey': 'LambdaS3Key',
                              'ParameterValue': pkg_name},
                             {'ParameterKey': 'LambdaTimeout',
                              'ParameterValue': str(config['timeout'])},
                             {'ParameterKey': 'LambdaMemorySize',
                              'ParameterValue': str(config['memory'])},
                             {'ParameterKey': 'APIName',
                              'ParameterValue': config['name']},
                             {'ParameterKey': 'APIDescription',
                              'ParameterValue': config['description']},
                             {'ParameterKey': 'APIBasePath',
                              'ParameterValue': config['base_path']}],
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_update_complete')
    try:
        waiter.wait(StackName=config['name'])
    except botocore.exceptions.ClientError:
        # the update failed, so we remove the lambda package from S3
        s3.delete_object(Bucket=bucket, Key=pkg_name)
        raise
    else:
        if previous_deployment:
            # the update succeeded, so it is safe to delete the lambda package
            # used in the previous deployment
            for p in previous_deployment['Parameters']:
                if p['ParameterKey'] == 'LambdaS3Key':
                    old_pkg = p['ParameterValue']
                    break
            s3.delete_object(Bucket=bucket, Key=old_pkg)


@main.command()
def template():
    """Print the default Cloudformation deployment template."""
    template = os.path.join(os.path.dirname(__file__), 'cfn.yaml')
    with open(template) as f:
        print(f.read())
