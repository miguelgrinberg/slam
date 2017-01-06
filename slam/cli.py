from __future__ import absolute_import

from datetime import datetime
import os
import re
import subprocess
import shutil
import sys

import boto3
import botocore
import climax
from lambda_uploader.package import build_package
import jinja2
import yaml


@climax.group()
@climax.argument('--config-file', '-c', default='slam.yaml',
                 help='The slam configuration file. Defaults to slam.yaml.')
def main(config_file):
    return {'config_file': config_file}


@main.command()
@climax.argument('--dynamodb-tables',
                 help='Comma-separated list of table names.')
@climax.argument('--requirements', default='requirements.txt',
                 help='The location of the project\'s requirements file.')
@climax.argument('--stages', default='dev',
                 help='Comma-separated list of stage environments to deploy.')
@climax.argument('--memory', type=int, default=128,
                 help=('The memory allocation for the lambda function in '
                       'megabytes.'))
@climax.argument('--timeout', type=int, default=10,
                 help='The timeout for the lambda function in seconds.')
@climax.argument('--bucket',
                 help='S3 bucket where lambda packages are stored.')
@climax.argument('--description', default='Deployed with slam.',
                 help='Description of the API.')
@climax.argument('--name',
                 help='API name.')
@climax.argument('wsgi_app',
                 help='The WSGI app instance, in the format module:app.')
def init(name, description, bucket, timeout, memory, stages, requirements,
         dynamodb_tables, wsgi_app, config_file):
    """Generate a configuration file."""
    if os.path.exists(config_file):
        print('Please delete the old version {} if you want to '
              'reconfigure your project.'.format(config_file))
        sys.exit(1)

    module, app = wsgi_app.split(':')
    if not name:
        name = module.replace('_', '-')
    if not re.match('^[a-zA-Z][-a-zA-Z0-9]*$', name):
        raise ValueError('The name {} is invalid, only letters, numbers and '
                         'dashes are allowed.'.format(name))
    if not bucket:
        bucket = name

    stages = [s.strip() for s in stages.split(',')]
    tables = [s.strip() for s in dynamodb_tables.split(',')] \
        if dynamodb_tables is not None else []

    # generate slam.yaml
    template_file = os.path.join(os.path.dirname(__file__),
                                 'templates/slam.yaml')
    with open(template_file) as f:
        template = f.read()
    template = jinja2.Environment(
        lstrip_blocks=True, trim_blocks=True).from_string(template).render(
            name=name, description=description, module=module, app=app,
            bucket=bucket, timeout=timeout, memory=memory,
            requirements=requirements, stages=stages, devstage=stages[0],
            tables=tables)
    with open(config_file, 'wt') as f:
        f.write(template)
    print('The configuration file for your project been generated. Remember '
          'to add {} to source control.'.format(config_file))


def _load_config(config_file='slam.yaml'):
    try:
        with open(config_file) as f:
            return yaml.load(f)
    except IOError:
        # there is no config file in the current directory
        raise RuntimeError('Config file {} not found. Did you run '
                           '"slam init"?'.format(config_file))


def _run_command(cmd):
    proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out, err = proc.communicate()
    if proc.returncode != 0:
        print(out)
        raise(RuntimeError('Command failed with exit code {}.'.format(
            proc.returncode)))


def _generate_lambda_handler(config):
    with open(os.path.join(os.path.dirname(__file__),
                           'templates/handler.py')) as f:
        template = f.read()
    template = jinja2.Environment(
        lstrip_blocks=True, trim_blocks=True).from_string(template).render(
            module=config['server_module'], app=config['server_app'])
    with open('.slam/handler.py', 'wt') as f:
        f.write(template)


def _build(config, rebuild_deps=False):
    package = datetime.utcnow().strftime("lambda_package.%Y%m%d_%H%M%S.zip")
    ignore = ['\.slam\/venv\/.*$', '\.pyc$']
    if os.environ.get('VIRTUAL_ENV'):
        # make sure the currently active virtualenv is not included in the pkg
        venv = os.path.relpath(os.environ['VIRTUAL_ENV'], os.getcwd())
        if not venv.startswith('.'):
            ignore.append(venv.replace('/', '\/') + '\/.*$')

    # create .slam directory if it doesn't exist yet
    if not os.path.exists('.slam'):
        os.mkdir('.slam')
    _generate_lambda_handler(config)

    # create or update virtualenv
    if rebuild_deps:
        if os.path.exists('.slam/venv'):
            shutil.rmtree('.slam/venv')
    if not os.path.exists('.slam/venv'):
        _run_command('virtualenv .slam/venv')
    _run_command('.slam/venv/bin/pip install -r ' + config['requirements'])

    # build lambda package
    build_package('.', config['requirements'], virtualenv='.slam/venv',
                  extra_files=['.slam/handler.py'], ignore=ignore,
                  zipfile_name=package)

    # cleanup lambda uploader's temp directory
    if os.path.exists('.lambda_uploader_temp'):
        shutil.rmtree('.lambda_uploader_temp')

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
    elif config.get('cfn_template'):
        template_file = config['cfn_template']
    else:
        template_file = os.path.join(os.path.dirname(__file__),
                                     'templates/cfn.yaml')
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
            stages=stages, devstage=config['devstage'], vars=vars,
            dynamodb_tables=config.get('dynamodb_tables') or {})
    return template


def _print_status(config):
    cfn = boto3.client('cloudformation')
    lmb = boto3.client('lambda')
    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        print('{} has not been deployed yet.'.format(config['name']))
    else:
        print('{} is deployed!'.format(config['name']))
        for s in config['stage_environments'].keys():
            fd = lmb.get_function(FunctionName=_get_from_stack(
                 stack, 'Output', 'FunctionArn'), Qualifier=s)
            v = fd['Configuration']['Version']
            if v != '$LATEST' and s != config['devstage']:
                v = '/v{}'.format(v)
            else:
                v = ''
            print('  {}{}: {}'.format(
                s, v, _get_from_stack(stack, 'Output',
                                      s.title() + 'Endpoint')))


@main.command()
@climax.argument('--rebuild-deps', action='store_true',
                 help='Reinstall all dependencies.')
def build(rebuild_deps, config_file):
    """Build lambda package."""
    config = _load_config(config_file)

    print("Building lambda package...")
    package = _build(config, rebuild_deps=rebuild_deps)
    print("{} has been built successfully.".format(package))


@main.command()
@climax.argument('--stage',
                 help='Stage to deploy. Defaults to the development stage.')
@climax.argument('--version',
                 help='Stage name or numeric version to set the stage to.')
@climax.argument('--template', help='Custom cloudformation template to '
                 'deploy.')
@climax.argument('--lambda-package',
                 help='Custom lambda zip package to deploy.')
@climax.argument('--no-lambda', action='store_true',
                 help='Do no deploy a new lambda.')
@climax.argument('--rebuild-deps', action='store_true',
                 help='Reinstall all dependencies.')
def deploy(stage, version, template, lambda_package, no_lambda, rebuild_deps,
           config_file):
    """Deploy project to AWS."""
    config = _load_config(config_file)

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')
    region = boto3.session.Session().region_name

    # obtain previous deployment if it exists
    previous_deployment = None
    try:
        previous_deployment = cfn.describe_stacks(
            StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        pass

    # validate input arguments and apply defaults
    if stage is None:
        stage = config['devstage']
    if stage != config['devstage']:
        if version is None:
            version = config['devstage']
        if version not in config['stage_environments'] and \
                not version.isdigit():
            raise ValueError('Version must be a stage name or number')
    else:
        if version is not None:
            raise ValueError('Version cannot be used when deploying to the '
                             'development stage.')

    # build lambda package if required
    built_package = False
    if stage == config['devstage'] and lambda_package is None and \
            not no_lambda:
        print("Building lambda package...")
        lambda_package = _build(config, rebuild_deps=rebuild_deps)
        built_package = True
    elif lambda_package is None:
        # preserve package from previous deployment
        lambda_package = _get_from_stack(previous_deployment, 'Parameter',
                                         'LambdaS3Key')

    # create S3 bucket if it doesn't exist yet
    bucket = config['bucket']
    try:
        s3.head_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={
            'LocationConstraint': region})

    # upload lambda package to S3
    if built_package:
        s3.upload_file(lambda_package, bucket, lambda_package)
        if built_package:
            # we created the package, so now that is on S3 we can delete it
            os.remove(lambda_package)

    # prepare cloudformation template
    template_body = _get_cfn_template(config, custom_template=template)
    parameters = [
        {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': bucket},
        {'ParameterKey': 'LambdaS3Key', 'ParameterValue': lambda_package},
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
            v = v or '$LATEST'
        else:
            if version.isdigit():
                # explicit version number
                v = str(version)
            elif version == config['devstage']:
                # publish a new version from $LATEST, and assign it to stage
                lmb = boto3.client('lambda')
                v = lmb.publish_version(FunctionName=_get_from_stack(
                    previous_deployment, 'Output', 'FunctionArn'))['Version']
            else:
                # publish version from a stage other than the devstage
                v = _get_from_stack(previous_deployment, 'Parameter',
                                    version.title() + 'Version')
        parameters.append({'ParameterKey': param, 'ParameterValue': v})

    # run the cloudformation template
    if previous_deployment is None:
        print('Deploying {}...'.format(config['name']))
        cfn.create_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_create_complete')
    else:
        print('Updating {}...'.format(config['name']))
        cfn.update_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_update_complete')

    # wait for cloudformation to do its thing
    try:
        waiter.wait(StackName=config['name'])
    except botocore.exceptions.ClientError:
        # the update failed, so we remove the lambda package from S3
        s3.delete_object(Bucket=bucket, Key=lambda_package)
        raise
    else:
        if previous_deployment:
            # the update succeeded, so it is safe to delete the lambda package
            # used by the previous deployment
            old_pkg = _get_from_stack(previous_deployment, 'Parameter',
                                      'LambdaS3Key')
            s3.delete_object(Bucket=bucket, Key=old_pkg)

    # we are done, show status info and exit
    _print_status(config)


@main.command()
def delete(config_file):
    """Delete the project."""
    config = _load_config(config_file)

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
        print('{} has been deleted, but the S3 bucket {} failed to '
              'delete.'.format(config['name'], bucket))
    else:
        print('{} has been deleted.'.format(config['name']))


@main.command()
def status(config_file):
    """Show deployment status for the project."""
    config = _load_config(config_file)
    _print_status(config)


@main.command()
@climax.argument('--raw', action='store_true',
                 help='Return template before it is processed with the '
                 'configuration')
def template(raw, config_file):
    """Print the default Cloudformation deployment template."""
    config = _load_config(config_file)
    print(_get_cfn_template(config, raw=raw))
