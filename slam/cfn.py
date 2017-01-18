import collections
import json


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


def _get_stage_variables(config, stage):
    if config['stage_environments'][stage]:
        stage_vars = config['stage_environments'][stage].copy()
    else:
        stage_vars = {}
    if 'STAGE' not in stage_vars:
        stage_vars['STAGE'] = stage
    return stage_vars


def _get_dynamodb_policies(config):
    if not config['aws'].get('dynamodb_tables'):
        return []
    resources = []
    for stage in config['stage_environments'].keys():
        for name, table in config['aws']['dynamodb_tables'].items():
            resources.append(
                {
                    'Fn::Join': [
                        '',
                        [
                            'arn:aws:dynamodb:',
                            {'Ref': 'AWS::Region'},
                            ':',
                            {'Ref': 'AWS::AccountId'},
                            ':table/',
                            {'Ref': '{}{}DynamoDBTable'.format(
                                stage.title(), name.title())}
                        ]
                    ]
                }
            )
    policy = {
        'PolicyName': 'DynamoDBPolicy',
        'PolicyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'dynamodb:DeleteItem',
                        'dynamodb:GetItem',
                        'dynamodb:PutItem',
                        'dynamodb:Query',
                        'dynamodb:Scan',
                        'dynamodb:UpdateItem'
                    ],
                    'Resource': resources
                }
            ]
        }
    }
    return [policy]


def _get_dynamodb_key_schema(key):
    key_schema = []
    if isinstance(key, list):
        for k in key:
            key_schema.append(
                {
                    'AttributeName': k,
                    'KeyType': 'HASH' if k == key[0] else 'RANGE'
                }
            )
    else:
        key_schema.append(
            {
                'AttributeName': key,
                'KeyType': 'HASH'
            }
        )
    return key_schema


def _get_dynamodb_projection(projection):
    if not projection:
        p = {
            'ProjectionType': 'KEYS_ONLY'
        }
    elif projection == 'all':
        p = {
            'ProjectionType': 'ALL'
        }
    else:
        p = {
            'ProjectionType': 'INCLUDE',
            'NonKeyAttributes': projection
        }
    return p


def _get_table_resource(config, stage, name):
    table = config['aws']['dynamodb_tables'][name]
    attributes = []
    for attr, attr_type in table['attributes'].items():
        attributes.append(
            {
                'AttributeName': attr,
                'AttributeType': attr_type
            }
        )
    read_units, write_units = table.get('provisioned_throughput', [1, 1])
    res = {
        'Type': 'AWS::DynamoDB::Table',
        'Properties': {
            'TableName': stage + '.' + name,
            'AttributeDefinitions': attributes,
            'KeySchema': _get_dynamodb_key_schema(table['key']),
            'ProvisionedThroughput': {
                'ReadCapacityUnits': read_units,
                'WriteCapacityUnits': write_units
            }
        }
    }
    if table.get('local_secondary_indexes'):
        idxs = []
        for name, index in table['local_secondary_indexes'].items():
            idx = {
                'IndexName': name,
                'KeySchema': _get_dynamodb_key_schema(index['key']),
                'Projection': _get_dynamodb_projection(index.get('projection'))
            }
            idxs.append(idx)
        res['Properties']['LocalSecondaryIndexes'] = idx
    if table.get('global_secondary_indexes'):
        idxs = []
        for name, index in table['global_secondary_indexes'].items():
            read_units, write_units = index.get('provisioned_throughput',
                                                [1, 1])
            idx = {
                'IndexName': name,
                'KeySchema': _get_dynamodb_key_schema(index['key']),
                'Projection': _get_dynamodb_projection(
                    index.get('projection')),
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': read_units,
                    'WriteCapacityUnits': write_units
                }
            }
            idxs.append(idx)
        res['Properties']['LocalSecondaryIndexes'] = idx
    return res


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
            'Policies': _get_dynamodb_policies(config)
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
                    'Variables': _get_stage_variables(config, stage)
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
        for name, table in config['aws'].get('dynamodb_tables', {}).items():
            res['{}{}DynamoDBTable'.format(stage.title(), name.title())] = \
                _get_table_resource(config, stage, name)
    return res


def _get_cfn_outputs(config):
    outputs = collections.OrderedDict()
    outputs['FunctionArn'] = {
        'Value': {'Fn::GetAtt': ['Function', 'Arn']}
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
    if pretty:
        return json.dumps(tpl, indent=4, separators=(',', ': '))
    return json.dumps(tpl)
