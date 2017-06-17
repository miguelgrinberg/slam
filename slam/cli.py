from __future__ import print_function

from datetime import datetime
import inspect
import json
import logging
import os
try:
    import pkg_resources
except ImportError:  # pragma: no cover
    pkg_resources = None
import random
import re
import subprocess
import shutil
import string
import sys
import time

import boto3
import botocore
import climax
from lambda_uploader.package import build_package
from merry import Merry
import yaml

from . import plugins
from .cfn import get_cfn_template
from .helpers import render_template

merry = Merry(logger_name='slam', debug='unittest' in sys.modules)
f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
h = logging.FileHandler('slam_error.log')
h.setFormatter(f)
merry.logger.addHandler(h)


@merry._try
@climax.group()
@climax.argument('--config-file', '-c', default='slam.yaml',
                 help='The slam configuration file. Defaults to slam.yaml.')
def main(config_file):
    return {'config_file': config_file}


@merry._except(RuntimeError, ValueError)
def on_error(e):  # pragma: no cover
    """Error handler

    RuntimeError or ValueError exceptions raised by commands will be handled
    by this function.
    """
    exname = {'RuntimeError': 'Runtime error', 'Value Error': 'Value error'}
    sys.stderr.write('{}: {}\n'.format(exname[e.__class__.__name__], str(e)))
    sys.stderr.write('See file slam_error.log for additional details.\n')
    sys.exit(1)


@merry._except(Exception)
def on_unexpected_error(e):  # pragma: no cover
    """Catch-all error handler

    Unexpected errors will be handled by this function.
    """
    sys.stderr.write('Unexpected error: {} ({})\n'.format(
        str(e), e.__class__.__name__))
    sys.stderr.write('See file slam_error.log for additional details.\n')
    sys.exit(1)


def _load_config(config_file='slam.yaml'):
    try:
        with open(config_file) as f:
            return yaml.load(f)
    except IOError:
        # there is no config file in the current directory
        raise RuntimeError('Config file {} not found. Did you run '
                           '"slam init"?'.format(config_file))


@main.command()
@climax.argument('--runtime', default=None,
                 help=('The Lambda runtime to use, such as python2.7 or '
                       'python3.6'))
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
@climax.argument('function',
                 help='The function or callable to deploy, in the format '
                      'module:function.')
def init(name, description, bucket, timeout, memory, stages, requirements,
         function, runtime, config_file, **kwargs):
    """Generate a configuration file."""
    if os.path.exists(config_file):
        raise RuntimeError('Please delete the old version {} if you want to '
                           'reconfigure your project.'.format(config_file))

    module, app = function.split(':')
    if not name:
        name = module.replace('_', '-')
    if not re.match('^[a-zA-Z][-a-zA-Z0-9]*$', name):
        raise ValueError('The name {} is invalid, only letters, numbers and '
                         'dashes are allowed.'.format(name))
    if not bucket:
        random_suffix = ''.join(
            random.choice(string.ascii_uppercase + string.digits)
            for n in range(8))
        bucket = '{}-{}'.format(name, random_suffix)

    stages = [s.strip() for s in stages.split(',')]

    if runtime is None:
        if sys.version_info[0] == 2:  # pragma: no cover
            runtime = 'python2.7'
        else:
            runtime = 'python3.6'

    # generate slam.yaml
    template_file = os.path.join(os.path.dirname(__file__),
                                 'templates/slam.yaml')
    with open(template_file) as f:
        template = f.read()
    template = render_template(template, name=name, description=description,
                               module=module, app=app, bucket=bucket,
                               timeout=timeout, memory=memory,
                               requirements=requirements, stages=stages,
                               devstage=stages[0], runtime=runtime)
    with open(config_file, 'wt') as f:
        f.write(template)

    # plugins
    config = _load_config(config_file)
    for name, plugin in plugins.items():
        # write plugin documentation as a comment in config file
        with open(config_file, 'at') as f:
            f.write('\n\n# ' + (plugin.__doc__ or name).replace(
                '\n', '\n# ') + '\n')
        if hasattr(plugin, 'init'):
            arguments = {k: v for k, v in kwargs.items()
                         if k in getattr(plugin.init, '_argnames', [])}
            plugin_config = plugin.init.func(config=config, **arguments)
            if plugin_config:
                with open(config_file, 'at') as f:
                    yaml.dump({name: plugin_config}, f,
                              default_flow_style=False)

    print('The configuration file for your project has been generated. '
          'Remember to add {} to source control.'.format(config_file))


def _run_command(cmd):
    try:
        proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        out, err = proc.communicate()
    except OSError:
        raise RuntimeError('Invalid command {}'.format(cmd))
    if proc.returncode != 0:
        print(out)
        raise(RuntimeError('Command failed with exit code {}.'.format(
            proc.returncode)))
    return out


def _run_lambda_function(event, context, app, config):  # pragma: no cover
    """Run the function. This is the default when no plugins (such as wsgi)
    define an alternative run function."""
    args = event.get('args', [])
    kwargs = event.get('kwargs', {})

    # first attempt to invoke the function passing the lambda event and context
    try:
        ret = app(*args, event=event, context=context, **kwargs)
    except TypeError:
        # try again without passing the event and context
        ret = app(*args, **kwargs)
    return ret


def _generate_lambda_handler(config, output='.slam/handler.py'):
    """Generate a handler.py file for the lambda function start up."""
    # Determine what the start up code is. The default is to just run the
    # function, but it can be overriden by a plugin such as wsgi for a more
    # elaborated way to run the function.
    run_function = _run_lambda_function
    for name, plugin in plugins.items():
        if name in config and hasattr(plugin, 'run_lambda_function'):
            run_function = plugin.run_lambda_function
    run_code = ''.join(inspect.getsourcelines(run_function)[0][1:])

    # generate handler.py
    with open(os.path.join(os.path.dirname(__file__),
                           'templates/handler.py.template')) as f:
        template = f.read()
    template = render_template(template, module=config['function']['module'],
                               app=config['function']['app'],
                               run_lambda_function=run_code,
                               config_json=json.dumps(config,
                                                      separators=(',', ':')))
    with open(output, 'wt') as f:
        f.write(template + '\n')


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


def _get_aws_region():  # pragma: no cover
    return boto3.session.Session().region_name


def _ensure_bucket_exists(s3, bucket, region):  # pragma: no cover
    try:
        s3.head_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError:
        if region != 'us-east-1':
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={
                'LocationConstraint': region})
        else:
            s3.create_bucket(Bucket=bucket)


def _get_from_stack(stack, source, key):
    value = None
    if source + 's' not in stack:
        raise ValueError('Invalid stack attribute' + str(stack))
    for p in stack[source + 's']:
        if p[source + 'Key'] == key:
            value = p[source + 'Value']
            break
    return value


def _print_status(config):
    cfn = boto3.client('cloudformation')
    lmb = boto3.client('lambda')
    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        print('{} has not been deployed yet.'.format(config['name']))
    else:
        print('{} is deployed!'.format(config['name']))
        print('  Function name: {}'.format(
            _get_from_stack(stack, 'Output', 'FunctionArn').split(':')[-1]))
        print('  S3 bucket: {}'.format(config['aws']['s3_bucket']))
        print('  Stages:')
        stages = list(config['stage_environments'].keys())
        stages.sort()
        plugin_status = {}
        for name, plugin in plugins.items():
            if name in config and hasattr(plugin, 'status'):
                statuses = plugin.status(config, stack)
                if statuses:
                    for s, status in statuses.items():
                        plugin_status.setdefault(s, []).append(status)
        for s in stages:
            fd = None
            try:
                fd = lmb.get_function(FunctionName=_get_from_stack(
                    stack, 'Output', 'FunctionArn'), Qualifier=s)
            except botocore.exceptions.ClientError:  # pragma: no cover
                continue
            v = ':{}'.format(fd['Configuration']['Version'])
            if s in plugin_status and len(plugin_status[s]) > 0:
                print('    {}{}: {}'.format(s, v,
                                            ' '.join(plugin_status[s])))
            else:
                print('    {}{}'.format(s, v))


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
                 help=('Stage to deploy to. Defaults to the stage designated '
                       'as the development stage'))
@climax.argument('--lambda-package',
                 help='Custom lambda zip package to deploy.')
@climax.argument('--no-lambda', action='store_true',
                 help='Do no deploy a new lambda.')
@climax.argument('--rebuild-deps', action='store_true',
                 help='Reinstall all dependencies.')
def deploy(stage, lambda_package, no_lambda, rebuild_deps, config_file):
    """Deploy the project to the development stage."""
    config = _load_config(config_file)
    if stage is None:
        stage = config['devstage']

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')
    region = _get_aws_region()

    # obtain previous deployment if it exists
    previous_deployment = None
    try:
        previous_deployment = cfn.describe_stacks(
            StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        pass

    # build lambda package if required
    built_package = False
    new_package = True
    if lambda_package is None and not no_lambda:
        print("Building lambda package...")
        lambda_package = _build(config, rebuild_deps=rebuild_deps)
        built_package = True
    elif lambda_package is None:
        # preserve package from previous deployment
        new_package = False
        lambda_package = _get_from_stack(previous_deployment, 'Parameter',
                                         'LambdaS3Key')

    # create S3 bucket if it doesn't exist yet
    bucket = config['aws']['s3_bucket']
    _ensure_bucket_exists(s3, bucket, region)

    # upload lambda package to S3
    if new_package:
        s3.upload_file(lambda_package, bucket, lambda_package)
        if built_package:
            # we created the package, so now that is on S3 we can delete it
            os.remove(lambda_package)

    # prepare cloudformation template
    template_body = get_cfn_template(config)
    parameters = [
        {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': bucket},
        {'ParameterKey': 'LambdaS3Key', 'ParameterValue': lambda_package},
    ]
    stages = list(config['stage_environments'].keys())
    stages.sort()
    for s in stages:
        param = s.title() + 'Version'
        if s != stage:
            v = _get_from_stack(previous_deployment, 'Parameter', param) \
                if previous_deployment else '$LATEST'
            v = v or '$LATEST'
        else:
            v = '$LATEST'
        parameters.append({'ParameterKey': param, 'ParameterValue': v})

    # run the cloudformation template
    if previous_deployment is None:
        print('Deploying {}:{}...'.format(config['name'], stage))
        cfn.create_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_create_complete')
    else:
        print('Updating {}:{}...'.format(config['name'], stage))
        cfn.update_stack(StackName=config['name'], TemplateBody=template_body,
                         Parameters=parameters,
                         Capabilities=['CAPABILITY_IAM'])
        waiter = cfn.get_waiter('stack_update_complete')

    # wait for cloudformation to do its thing
    try:
        waiter.wait(StackName=config['name'])
    except botocore.exceptions.ClientError:
        # the update failed, so we remove the lambda package from S3
        if built_package:
            s3.delete_object(Bucket=bucket, Key=lambda_package)
        raise
    else:
        if previous_deployment and new_package:
            # the update succeeded, so it is safe to delete the lambda package
            # used by the previous deployment
            old_pkg = _get_from_stack(previous_deployment, 'Parameter',
                                      'LambdaS3Key')
            s3.delete_object(Bucket=bucket, Key=old_pkg)

    # we are done, show status info and exit
    _print_status(config)


@main.command()
@climax.argument('--version',
                 help=('Stage name or numeric version to publish. '
                       'Defaults to the development stage.'))
@climax.argument('stage', help='Stage to publish to.')
def publish(version, stage, config_file):
    """Publish a version of the project to a stage."""
    config = _load_config(config_file)
    cfn = boto3.client('cloudformation')

    if version is None:
        version = config['devstage']
    elif version not in config['stage_environments'].keys() and \
            not version.isdigit():
        raise ValueError('Invalid version. Use a stage name or a numeric '
                         'version number.')
    if version == stage:
        raise ValueError('Cannot deploy a stage into itself.')

    # obtain previous deployment
    try:
        previous_deployment = cfn.describe_stacks(
            StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        raise RuntimeError('This project has not been deployed yet.')

    # preserve package from previous deployment
    bucket = _get_from_stack(previous_deployment, 'Parameter',
                             'LambdaS3Bucket')
    lambda_package = _get_from_stack(previous_deployment, 'Parameter',
                                     'LambdaS3Key')

    # prepare cloudformation template
    template_body = get_cfn_template(config)
    parameters = [
        {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': bucket},
        {'ParameterKey': 'LambdaS3Key', 'ParameterValue': lambda_package},
    ]
    stages = list(config['stage_environments'].keys())
    stages.sort()
    for s in stages:
        param = s.title() + 'Version'
        if s != stage:
            v = _get_from_stack(previous_deployment, 'Parameter', param) \
                if previous_deployment else '$LATEST'
            v = v or '$LATEST'
        else:
            if version.isdigit():
                # explicit version number
                v = version
            else:
                # publish version from a stage
                v = _get_from_stack(previous_deployment, 'Parameter',
                                    version.title() + 'Version')
                if v == '$LATEST':
                    # publish a new version from $LATEST
                    lmb = boto3.client('lambda')
                    v = lmb.publish_version(FunctionName=_get_from_stack(
                        previous_deployment, 'Output', 'FunctionArn'))[
                            'Version']
        parameters.append({'ParameterKey': param, 'ParameterValue': v})

    # run the cloudformation template
    print('Publishing {}:{} to {}...'.format(config['name'], version, stage))
    cfn.update_stack(StackName=config['name'], TemplateBody=template_body,
                     Parameters=parameters,
                     Capabilities=['CAPABILITY_IAM'])
    waiter = cfn.get_waiter('stack_update_complete')

    # wait for cloudformation to do its thing
    try:
        waiter.wait(StackName=config['name'])
    except botocore.exceptions.ClientError:
        raise

    # we are done, show status info and exit
    _print_status(config)


@main.command()
@climax.argument('args', nargs='*',
                 help='Input arguments for the function. Use arg=value for '
                      'strings, or arg:=value for integer, booleans or JSON '
                      'structures.')
@climax.argument('--dry-run', action='store_true',
                 help='Just check that the function can be invoked.')
@climax.argument('--async', action='store_true',
                 help='Invoke the function but don\'t wait for it to return.')
@climax.argument('--stage', help='Stage of the invoked function. Defaults to '
                                 'the development stage')
def invoke(stage, async, dry_run, config_file, args):
    """Invoke the lambda function."""
    config = _load_config(config_file)
    if stage is None:
        stage = config['devstage']

    cfn = boto3.client('cloudformation')
    lmb = boto3.client('lambda')

    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        raise RuntimeError('This project has not been deployed yet.')
    function = _get_from_stack(stack, 'Output', 'FunctionArn')

    if dry_run:
        invocation_type = 'DryRun'
    elif async:
        invocation_type = 'Event'
    else:
        invocation_type = 'RequestResponse'

    # parse input arguments
    data = {}
    for arg in args:
        s = arg.split('=', 1)
        if len(s) != 2:
            raise ValueError('Invalid argument ' + arg)
        if s[0][-1] == ':':
            # JSON argument
            data[s[0][:-1]] = json.loads(s[1])
        else:
            # string argument
            data[s[0]] = s[1]

    rv = lmb.invoke(FunctionName=function, InvocationType=invocation_type,
                    Qualifier=stage,
                    Payload=json.dumps({'kwargs': data}, sort_keys=True))
    if rv['StatusCode'] != 200 and rv['StatusCode'] != 202:
        raise RuntimeError('Unexpected error. Status code = {}.'.format(
            rv['StatusCode']))
    if invocation_type == 'RequestResponse':
        payload = json.loads(rv['Payload'].read().decode('utf-8'))
        if 'FunctionError' in rv:
            if 'stackTrace' in payload:
                print('Traceback (most recent call last):')
                for frame in payload['stackTrace']:
                    print('  File "{}", line {}, in {}'.format(
                        frame[0], frame[1], frame[2]))
                    print('    ' + frame[3])
                print('{}: {}'.format(payload['errorType'],
                                      payload['errorMessage']))
            else:
                raise RuntimeError('Unknown error')
        else:
            print(str(payload))


@main.command()
@climax.argument('--no-logs', action='store_true', help='Do not delete logs.')
def delete(no_logs, config_file):
    """Delete the project."""
    config = _load_config(config_file)

    s3 = boto3.client('s3')
    cfn = boto3.client('cloudformation')
    logs = boto3.client('logs')

    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        raise RuntimeError('This project has not been deployed yet.')
    bucket = _get_from_stack(stack, 'Parameter', 'LambdaS3Bucket')
    lambda_package = _get_from_stack(stack, 'Parameter', 'LambdaS3Key')
    function = _get_from_stack(stack, 'Output', 'FunctionArn').split(':')[-1]
    api_id = _get_from_stack(stack, 'Output', 'ApiId')
    if api_id:
        log_groups = ['API-Gateway-Execution-Logs_' + api_id + '/' + stage
                      for stage in config['stage_environments'].keys()]
    else:
        log_groups = []
    log_groups.append('/aws/lambda/' + function)

    print('Deleting {}...'.format(config['name']))
    cfn.delete_stack(StackName=config['name'])
    waiter = cfn.get_waiter('stack_delete_complete')
    waiter.wait(StackName=config['name'])

    if not no_logs:
        print('Deleting logs...')
        for log_group in log_groups:
            try:
                logs.delete_log_group(logGroupName=log_group)
            except botocore.exceptions.ClientError:
                print('  Log group {} could not be deleted.'.format(log_group))

    print('Deleting files...')
    try:
        s3.delete_object(Bucket=bucket, Key=lambda_package)
        s3.delete_bucket(Bucket=bucket)
    except botocore.exceptions.ClientError:
        print('  S3 bucket {} could not be deleted.'.format(bucket))


@main.command()
def status(config_file):
    """Show deployment status for the project."""
    config = _load_config(config_file)
    _print_status(config)


@main.command()
@climax.argument('--tail', '-t', action='store_true',
                 help='Tail the log stream')
@climax.argument('--period', '-p', default='1m',
                 help=('How far back to start, in weeks (1w), days (2d), '
                       'hours (3h), minutes (4m) or seconds (5s). Default '
                       'is 1m.'))
@climax.argument('--stage',
                 help=('Stage to show logs for. Defaults to the stage '
                       'designated as the development stage'))
def logs(stage, period, tail, config_file):
    """Dump logs to the console."""
    config = _load_config(config_file)
    if stage is None:
        stage = config['devstage']

    cfn = boto3.client('cloudformation')
    try:
        stack = cfn.describe_stacks(StackName=config['name'])['Stacks'][0]
    except botocore.exceptions.ClientError:
        print('{} has not been deployed yet.'.format(config['name']))
        return
    function = _get_from_stack(stack, 'Output', 'FunctionArn').split(':')[-1]
    version = _get_from_stack(stack, 'Parameter', stage.title() + 'Version')
    api_id = _get_from_stack(stack, 'Output', 'ApiId')

    try:
        start = float(period[:-1])
    except ValueError:
        raise ValueError('Invalid period ' + period)
    if period[-1] == 's':
        start = time.time() - start
    elif period[-1] == 'm':
        start = time.time() - start * 60
    elif period[-1] == 'h':
        start = time.time() - start * 60 * 60
    elif period[-1] == 'd':
        start = time.time() - start * 60 * 60 * 24
    elif period[-1] == 'w':
        start = time.time() - start * 60 * 60 * 24 * 7
    else:
        raise ValueError('Invalid period ' + period)
    start = int(start * 1000)

    logs = boto3.client('logs')
    lambda_log_group = '/aws/lambda/' + function
    log_groups = [lambda_log_group]
    if api_id:
        log_groups.append('API-Gateway-Execution-Logs_' + api_id + '/' + stage)
    log_version = '[' + version + ']'
    log_start = {g: start for g in log_groups}
    while True:
        kwargs = {}
        events = []
        for log_group in log_groups:
            while True:
                try:
                    l = logs.filter_log_events(logGroupName=log_group,
                                               startTime=log_start[log_group],
                                               interleaved=True, **kwargs)
                except botocore.exceptions.ClientError:
                    # the log group does not exist yet
                    l = {'events': []}
                if log_group == lambda_log_group:
                    events += [ev for ev in l['events']
                               if log_version in ev['logStreamName']]
                else:
                    events += l['events']
                if len(l['events']):
                    log_start[log_group] = l['events'][-1]['timestamp'] + 1
                if 'nextToken' not in l:
                    break
                kwargs['nextToken'] = l['nextToken']
        events.sort(key=lambda ev: ev['timestamp'])
        for ev in events:
            tm = datetime.fromtimestamp(ev['timestamp'] / 1000)
            print(tm.strftime('%b %d %X ') + ev['message'].strip())
        if not tail:
            break
        time.sleep(5)


@main.command()
def template(config_file):
    """Print the default Cloudformation deployment template."""
    config = _load_config(config_file)
    print(get_cfn_template(config, pretty=True))


def register_plugins():
    """find any installed plugins and register them."""
    if pkg_resources:  # pragma: no cover
        for ep in pkg_resources.iter_entry_points('slam_plugins'):
            plugin = ep.load()

            # add any init options to the main init command
            if hasattr(plugin, 'init') and hasattr(plugin.init, '_arguments'):
                for arg in plugin.init._arguments:
                    init.parser.add_argument(*arg[0], **arg[1])
                init._arguments += plugin.init._arguments
                init._argnames += plugin.init._argnames

            plugins[ep.name] = plugin


register_plugins()  # pragma: no cover
