import collections
import json

from . import plugins


def _get_cfn_parameters(config):
    params = collections.OrderedDict()
    params['LambdaS3Bucket'] = {
        'Type': 'String',
        'Description': 'The S3 bucket where the lambda zip file is stored.'
    }
    params['LambdaS3Key'] = {
        'Type': 'String',
        'Description': 'The S3 key of the lambda zip file.'
    }
    for stage in config['stage_environments'].keys():
        params[stage.title() + 'Version'] = {
            'Type': 'String',
            'Description': ('The lambda version number associated with the {} '
                            'stage.').format(stage),
            'Default': '$LATEST'
        }
    return params


def _get_cfn_resources(config):
    res = collections.OrderedDict()
    res['FunctionExecutionRole'] = {
        'Type': 'AWS::IAM::Role',
        'Properties': {
            'AssumeRolePolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Principal': {
                            'Service': ['lambda.amazonaws.com']
                        },
                        'Action': 'sts:AssumeRole'
                    }
                ]
            },
            'ManagedPolicyArns': [
                ('arn:aws:iam::aws:policy/service-role/'
                 'AWSLambdaBasicExecutionRole')
            ],
            'Policies': []
        }
    }
    for policy in config['aws'].get('lambda_managed_policies') or []:
        if not policy.startswith('arn:'):
            policy_arn = 'arn:aws:iam::aws:policy/service-role/' + policy
        else:
            policy_arn = policy
        res['FunctionExecutionRole']['Properties']['ManagedPolicyArns'].append(
            policy_arn)
    for policy in config['aws'].get('lambda_inline_policies') or []:
        res['FunctionExecutionRole']['Properties']['Policies'].append(
            policy)
    res['Function'] = {
        'Type': 'AWS::Lambda::Function',
        'DependsOn': 'FunctionExecutionRole',
        'Properties': {
            'Code': {
                'S3Bucket': {'Ref': 'LambdaS3Bucket'},
                'S3Key': {'Ref': 'LambdaS3Key'}
            },
            'Role': {'Fn::GetAtt': ['FunctionExecutionRole', 'Arn']},
            'Timeout': config['aws'].get('lambda_timeout', 10),
            'MemorySize': config['aws'].get('lambda_memory', 128),
            'Handler': 'handler.lambda_handler',
            'Runtime': config['aws'].get('lambda_runtime', 'python2.7')
        }
    }
    if config['aws'].get('lambda_security_groups') or \
            config['aws'].get('lambda_subnet_ids'):
        res['FunctionExecutionRole']['Properties']['ManagedPolicyArns'].append(
            'arn:aws:iam::aws:policy/service-role/'
            'AWSLambdaVPCAccessExecutionRole')
        res['Function']['Properties']['VpcConfig'] = {
            'SecurityGroupIds':
                config['aws'].get('lambda_security_groups') or [],
            'SubnetIds': config['aws'].get('lambda_subnet_ids') or []
        }
    for stage in config['stage_environments'].keys():
        res[stage.title() + 'FunctionAlias'] = {
            'Type': 'AWS::Lambda::Alias',
            'Properties': {
                'Name': stage,
                'FunctionName': {'Ref': 'Function'},
                'FunctionVersion': {'Ref': stage.title() + 'Version'}
            }
        }
    res.update(config['aws'].get('cfn_resources') or {})
    return res


def _get_cfn_outputs(config):
    outputs = collections.OrderedDict()
    outputs['FunctionArn'] = {
        'Value': {'Fn::GetAtt': ['Function', 'Arn']}
    }
    outputs.update(config['aws'].get('cfn_outputs') or {})
    return outputs


def get_cfn_template(config, pretty=False):
    tpl = collections.OrderedDict(
        [
            ('AWSTemplateFormatVersion', '2010-09-09'),
            ('Parameters', _get_cfn_parameters(config)),
            ('Resources', _get_cfn_resources(config)),
            ('Outputs', _get_cfn_outputs(config))
        ]
    )
    for name, plugin in plugins.items():
        if name in config and hasattr(plugin, 'cfn_template'):
            tpl = plugin.cfn_template(config, tpl)
    if pretty:
        return json.dumps(tpl, indent=4, separators=(',', ': '))
    return json.dumps(tpl)
