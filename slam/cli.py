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
import jinja2


@climax.group()
def main():
    pass


@main.command()
@climax.argument('--name',
                 help='API name. A random name is used if this is not given.')
@climax.argument('--description', default='Deployed with slam.',
                 help='Description of the API.')
@climax.argument('--stages', default='dev',
                 help='Comma-separated list of stage environments to deploy.')
@climax.argument('--timeout', type=int, default=5,
                 help='The timeout for the lambda function in seconds.')
@climax.argument('--memory', type=int, default=128,
                 help=('The memory allocation for the lambda function in '
                       'megabytes.'))
@climax.argument('--requirements', default='requirements.txt',
                 help='The location of the project\'s requirements file.')
@climax.argument('wsgi_app',
                 help='The WSGI app instance, in the format module:app.')
def init(name, description, stages, timeout, memory, requirements,
         wsgi_app):
    """Generate handler.py file with configuration."""
    if os.path.exists('handler.py'):
        print('handler.py file exists! Please delete old version if you want '
              'to regenerate it.')
        sys.exit(1)

    handler = """import os

config = {{
    'name': '{name}',
    'description': '{description}',
    'timeout': {timeout},
    'memory': {memory},
    'requirements': '{requirements}',
    'devstage': '{devstage}',
    'environment': {{
        # insert variables common to all stages here
    }},
    'stage_environments': {{{stage_environments}
    }}
}}

if os.environ.get('LAMBDA_TASK_ROOT'):
    from slam import lambda_handler
    from {module} import {app}
    lambda_handler.app = {app}
"""
    stage_env = """
        '{stage}': {{
            # insert variables for the {stage} stage here
            'STAGE': '{stage}',
        }},"""

    module, app = wsgi_app.split(':')
    if not name:
        name = module
    name += '-' + ''.join(random.choice(
            string.ascii_lowercase + string.digits) for _ in range(6))
    stages = [s.strip() for s in stages.split(',')]
    stage_environments = ''
    for stage in stages:
        stage_environments += stage_env.format(stage=stage)

    with open('handler.py', 'wt') as f:
        f.write(handler.format(module=module, app=app, name=name,
                               description=description.replace("'", "\'"),
                               timeout=timeout, memory=memory,
                               requirements=requirements, devstage=stages[0],
                               stage_environments=stage_environments))
    print('A handler.py for your lambda server has been generated. Please '
          'add it to source control.')


def _load_config():
    saved_sys_path = sys.path
    sys.path = [os.getcwd()]
    from handler import config
    sys.path = saved_sys_path
    return config


def _build(config):
    package = datetime.utcnow().strftime("lambda_package.%Y%m%d_%H%M%S.zip")
    ignore = ['\\.pyc$']
    if os.environ.get('VIRTUAL_ENV'):
        # make sure the currently active virtualenv is not included in the pkg
        venv = os.path.relpath(os.environ['VIRTUAL_ENV'], os.getcwd())
        if not venv.startswith('.'):
            ignore.append(venv.replace('/', '\/') + '\/.*$')
    build_package('.', config['requirements'], ignore=ignore,
                  zipfile_name=package)
    return package


def _get_from_stack(stack, source, key):
    value = None
    for p in stack[source + 's']:
        if p[source + 'Key'] == key:
            value = p[source + 'Value']
            break
    return value


def _get_cfn_template(config, raw=False, custom_template=None):
    if custom_template:
        template_file = custom_template
    else:
        template_file = os.path.join(os.path.dirname(__file__), 'cfn.yaml')
    with open(template_file) as f:
        template = f.read()
    if raw:
        return template
    stages = config['stage_environments'].keys()
    vars = config['stage_environments'].copy()
    for s in config['stage_environments'].keys():
        vars[s] = config['environment'].copy()
        vars[s].update(config['stage_environments'][s])

    template = jinja2.Environment(
        lstrip_blocks=True, trim_blocks=True).from_string(template).render(
            stages=stages, devstage=config['devstage'], vars=vars)
    return template


def _print_status(config):
    cfn = boto3.client('cloudformation')
    lmb = boto3.client('lambda')
    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        print('The API has not been deployed yet.')
    else:
        # determine if $LATEST has been published as a stage version, as in
        # that case we want to show the version number
        f = {}
        for s in config['stage_environments'].keys():
            fd = lmb.get_function(FunctionName=_get_from_stack(
                 stack, 'Output', 'FunctionArn'), Qualifier=s)
            f[s] = {'s': fd['Configuration']['CodeSha256'],
                    'v': fd['Configuration']['Version']}
        for s in config['stage_environments'].keys():
            if f[s]['v'] == '$LATEST':
                for t in config['stage_environments'].keys():
                    if s != t and not f[t]['v'].startswith('$LATEST') and f[s]['s'] == f[t]['s']:
                        f[s]['v'] += '/' + f[t]['v']
                        break
        for s in config['stage_environments'].keys():
            if f[s]['v'].startswith('$LATEST') and config['devstage'] != s:
                f[s]['v'] = 'None'

        print('Your API is deployed!')
        for s in config['stage_environments'].keys():
            print('  {}/{}: {}'.format(s, f[s]['v'], _get_from_stack(
                stack, 'Output', s.title() + 'Endpoint')))


@main.command()
def build():
    """Build lambda package."""
    config = _load_config()

    print("Building lambda package...")
    package = _build(config)
    print("{} has been built successfully.".format(package))


@main.command()
@climax.argument('--template', help='Custom cloudformation template to '
                 'deploy.')
@climax.argument('--package', help='Custom lambda zip package to deploy.')
@climax.argument('--stage',
                 help='Stage to deploy. Defaults to the development stage.')
@climax.argument('--version',
                 help='Stage or numeric version to set the stage to.')
def deploy(template, package, stage, version):
    """Deploy API to AWS."""
    config = _load_config()

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')
    region = boto3.session.Session().region_name

    if stage is None:
        stage = config['devstage']
    if stage != config['devstage']:
        if version is None:
            raise RuntimeError('Must provide version argument.')
        if version not in config['stage_environments'] and \
                not version.isdigit():
            raise RuntimeError('Version must be a stage name or number')

    # determine if this is a new deployment or an update
    previous_deployment = None
    try:
        previous_deployment = cfn.describe_stacks(
            StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        pass

    built_package = False
    if package is None and stage == config['devstage']:
        print("Building lambda package...")
        package = _build(config)
        built_package = True
    elif stage != config['devstage']:
        package = _get_from_stack(previous_deployment, 'Parameter',
                                  'LambdaS3Key')

    if previous_deployment:
        bucket = _get_from_stack(previous_deployment, 'Parameter',
                                 'LambdaS3Bucket')
    else:
        if stage != config['devstage']:
            raise RuntimeError('Must deploy {} stage first.'.format(
                config['devstage']))

        bucket = config['name']
        try:
            s3.head_bucket(Bucket=bucket)
        except botocore.exceptions.ClientError:
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={
                'LocationConstraint': region})

    # upload pkg to s3
    if stage == config['devstage']:
        s3.upload_file(package, bucket, package)
        if built_package:
            # we created the package, so now that is on S3 we can delete it
            os.remove(package)

    if template is None:
        template_body = _get_cfn_template(config)
    else:
        with open(template) as f:
            template_body = f.read()

    parameters = [
        {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': bucket},
        {'ParameterKey': 'LambdaS3Key', 'ParameterValue': package},
        {'ParameterKey': 'LambdaTimeout',
         'ParameterValue': str(config['timeout'])},
        {'ParameterKey': 'LambdaMemorySize',
         'ParameterValue': str(config['memory'])},
        {'ParameterKey': 'APIName', 'ParameterValue': config['name']},
        {'ParameterKey': 'APIDescription',
         'ParameterValue': config['description']},
    ]
    for s in config['stage_environments'].keys():
        if s == config['devstage']:
            # the dev stage always gets the latest version
            continue
        param = s.title() + 'Version'
        if s != stage:
            v = _get_from_stack(previous_deployment, 'Parameter', param) \
                if previous_deployment else '$LATEST'
        else:
            if version.isdigit():
                v = str(version)
            elif version == config['devstage']:
                # publish a new version from $LATEST, and assign it to stage
                lmb = boto3.client('lambda')
                v = lmb.publish_version(FunctionName=_get_from_stack(
                    previous_deployment, 'Output', 'FunctionArn'))['Version']
            else:
                v = _get_from_stack(previous_deployment, 'Parameter',
                                    version.title() + 'Version')
        parameters.append({'ParameterKey': param, 'ParameterValue': v})

    if previous_deployment is None:
        print("Deploying API...")
        cfn.create_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_create_complete')
    else:
        print("Updating API...")
        cfn.update_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_update_complete')
    try:
        waiter.wait(StackName=config['name'])
    except botocore.exceptions.ClientError:
        # the update failed, so we remove the lambda package from S3
        s3.delete_object(Bucket=bucket, Key=package)
        raise
    else:
        if previous_deployment:
            # the update succeeded, so it is safe to delete the lambda package
            # used in the previous deployment
            old_pkg = _get_from_stack(previous_deployment, 'Parameter',
                                      'LambdaS3Key')
            s3.delete_object(Bucket=bucket, Key=old_pkg)

    _print_status(config)


@main.command()
def delete():
    """Delete an API."""
    config = _load_config()

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')

    stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    bucket = _get_from_stack(stack, 'Parameter', 'LambdaS3Bucket')
    old_pkg = _get_from_stack(stack, 'Parameter', 'LambdaS3Key')

    print('Deleting API...')
    cfn.delete_stack(StackName=config['name'])
    waiter = cfn.get_waiter('stack_delete_complete')
    waiter.wait(StackName=config['name'])

    try:
        s3.delete_object(Bucket=bucket, Key=old_pkg)
        s3.delete_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError:
        print('The API has been deleted, but the S3 bucket "{}" failed to '
              'delete.'.format(bucket))
    else:
        print('The API has been deleted.')


@main.command()
def status():
    """Show deployment status for the API."""
    config = _load_config()
    _print_status(config)


@main.command()
@climax.argument('--raw', action='store_true',
                 help='Return template before it is processed')
def template(raw):
    """Print the default Cloudformation deployment template."""
    config = _load_config()
    print(_get_cfn_template(config, raw=raw))
