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
            'Runtime': 'python2.7'
        }
    }
    res['API'] = {
        'Type': 'AWS::ApiGateway::RestApi',
        'Properties': {
            'Body': {
                'swagger': '2.0',
                'info': {
                    'title': config['name'],
                    'description': config.get('description', '')
                },
                'schemes': ['https'],
                'paths': {
                    '/': {
                        'x-amazon-apigateway-any-method': {
                            'responses': {},
                            'x-amazon-apigateway-integration': {
                                'responses': {
                                    'default': {
                                        'statusCode': '200'
                                    }
                                },
                                'uri': {
                                    'Fn::Join': [
                                        '',
                                        [
                                            'arn:aws:apigateway:',
                                            {'Ref': 'AWS::Region'},
                                            (':lambda:path/2015-03-31/'
                                             'functions/'),
                                            {'Fn::GetAtt': ['Function',
                                                            'Arn']},
                                            (':${stageVariables.STAGE}/'
                                             'invocations')
                                        ]
                                    ]
                                },
                                'passthroughBehavior': 'when_no_match',
                                'httpMethod': 'POST',
                                'type': 'aws_proxy'
                            }
                        }
                    },
                    '/{proxy+}': {
                        'x-amazon-apigateway-any-method': {
                            'parameters': [
                                {
                                    'name': 'proxy',
                                    'in': 'path',
                                    'required': True,
                                    'type': 'string'
                                }
                            ],
                            'responses': {},
                            'x-amazon-apigateway-integration': {
                                'responses': {
                                    'default': {
                                        'statusCode': '200'
                                    }
                                },
                                'uri': {
                                    'Fn::Join': [
                                        '',
                                        [
                                            'arn:aws:apigateway:',
                                            {'Ref': 'AWS::Region'},
                                            (':lambda:path/2015-03-31/'
                                             'functions/'),
                                            {'Fn::GetAtt': ['Function',
                                                            'Arn']},
                                            (':${stageVariables.STAGE}/'
                                             'invocations')
                                        ]
                                    ]
                                },
                                'passthroughBehavior': 'when_no_match',
                                'httpMethod': 'POST',
                                'type': 'aws_proxy'
                            }
                        }
                    }
                }
            }
        }
    }
    res['APICloudWatchRole'] = {
        'Type': 'AWS::IAM::Role',
        'Properties': {
            'AssumeRolePolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Principal': {
                            'Service': ['apigateway.amazonaws.com']
                        },
                        'Action': 'sts:AssumeRole'
                    }
                ]
            },
            'Path': '/',
            'ManagedPolicyArns': ['arn:aws:iam::aws:policy/service-role/'
                                  'AmazonAPIGatewayPushToCloudWatchLogs']
        }
    }
    res['APIAccount'] = {
        'Type': 'AWS::ApiGateway::Account',
        'DependsOn': 'API',
        'Properties': {
            'CloudWatchRoleArn': {
                'Fn::GetAtt': ['APICloudWatchRole', 'Arn']
            }
        }
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
        res[stage.title() + 'APIDeployment'] = {
            'Type': 'AWS::ApiGateway::Deployment',
            'Properties': {
                'RestApiId': {'Ref': 'API'},
                'StageName': stage,
                'StageDescription': {
                    'MethodSettings': [
                        {
                            'ResourcePath': '/*',
                            'HttpMethod': '*',
                            'LoggingLevel': 'INFO'
                            if stage == config['devstage'] else 'ERROR',
                        }
                    ],
                    'Variables': {
                        'STAGE': stage
                    }
                }
            }
        }
        res[stage.title() + 'APILambdaPermission'] = {
            'Type': 'AWS::Lambda::Permission',
            'DependsOn': stage.title() + 'FunctionAlias',
            'Properties': {
                'Action': 'lambda:InvokeFunction',
                'FunctionName': {'Ref': stage.title() + 'FunctionAlias'},
                'Principal': 'apigateway.amazonaws.com',
                'SourceArn': {
                    'Fn::Join': [
                        '',
                        [
                            'arn:aws:execute-api:',
                            {'Ref': 'AWS::Region'},
                            ':',
                            {'Ref': 'AWS::AccountId'},
                            ':',
                            {'Ref': 'API'},
                            '/*/*/*'
                        ]
                    ]
                }
            }
        }
    return res


def _get_cfn_outputs(config):
    outputs = collections.OrderedDict()
    outputs['FunctionArn'] = {
        'Value': {'Fn::GetAtt': ['Function', 'Arn']}
    }
    outputs['ApiId'] = {
        'Value': {'Ref': 'API'}
    }
    for stage in config['stage_environments'].keys():
        outputs[stage.title() + 'Endpoint'] = {
            'Value': {
                'Fn::Join': [
                    '',
                    [
                        'https://',
                        {'Ref': 'API'},
                        '.execute-api.',
                        {'Ref': 'AWS::Region'},
                        '.amazonaws.com/' + stage
                    ]
                ]
            }
        }
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
