"""DynamoDB Plugin

This plugin provisions DynamoDB tables for each stage.

dynamodb_tables:
  # a simple table with a single id key:
  mytable:
    attributes:
      id: "S"
    key: "id"
    read_throughput: 1
    write_throughput: 1

  # a more complex example:
  mytable2:
   attributes:
     id: "S"
     name: "S"
     age: "N"
   key: ["id", "name"]
   read_throughput: 1
   write_throughput: 1
   local_secondary_indexes:
     myindex:
       key: ["id", "age"]
       project:
         - "name"
   global_secondary_indexes:
     myindex2:
       key: ["age", "name"]
       project: "all"
       read_throughput: 1
       write_throughput: 1
"""
import climax


@climax.command()
@climax.argument('--dynamodb-tables',
                 help=('Comma-separated list of table names to create for '
                       'each stage.'))
def init(config, dynamodb_tables):
    tables = [s.strip() for s in dynamodb_tables.split(',')] \
        if dynamodb_tables is not None else []
    if not tables:
        return
    table_config = {}
    for table in tables:
        table_config[table] = {
            'attributes': {'id': 'S'},
            'key': 'id',
            'read_throughput': 1,
            'write_throughput': 1
        }
    return table_config


def _get_dynamodb_policies(config):
    if not config.get('dynamodb_tables'):
        return []
    resources = []
    for stage in config['stage_environments'].keys():
        for name, table in config['dynamodb_tables'].items():
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
                        'dynamodb:UpdateItem',
                        'dynamodb:DescribeTable'
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


def _get_dynamodb_projection(project):
    if not project:
        p = {
            'ProjectionType': 'KEYS_ONLY'
        }
    elif project == 'all':
        p = {
            'ProjectionType': 'ALL'
        }
    else:
        p = {
            'ProjectionType': 'INCLUDE',
            'NonKeyAttributes': project
        }
    return p


def _get_table_resource(config, stage, name):
    table = config['dynamodb_tables'][name]
    attributes = []
    for attr, attr_type in table['attributes'].items():
        attributes.append(
            {
                'AttributeName': attr,
                'AttributeType': attr_type
            }
        )
    read_units = table.get('read_throughput', 1)
    write_units = table.get('write_throughput', 1)
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
                'Projection': _get_dynamodb_projection(index.get('project'))
            }
            idxs.append(idx)
        res['Properties']['LocalSecondaryIndexes'] = idxs
    if table.get('global_secondary_indexes'):
        idxs = []
        for name, index in table['global_secondary_indexes'].items():
            read_units = index.get('read_throughput', 1)
            write_units = index.get('write_throughput', 1)
            idx = {
                'IndexName': name,
                'KeySchema': _get_dynamodb_key_schema(index['key']),
                'Projection': _get_dynamodb_projection(
                    index.get('project')),
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': read_units,
                    'WriteCapacityUnits': write_units
                }
            }
            idxs.append(idx)
        res['Properties']['GlobalSecondaryIndexes'] = idxs
    return res


def cfn_template(config, template):
    res = template['Resources']
    for stage in config['stage_environments'].keys():
        for name, table in config.get('dynamodb_tables', {}).items():
            res['{}{}DynamoDBTable'.format(stage.title(), name.title())] = \
                _get_table_resource(config, stage, name)
    res['FunctionExecutionRole']['Properties']['Policies'].extend(
        _get_dynamodb_policies(config))
    return template
