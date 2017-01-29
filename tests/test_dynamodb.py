from copy import deepcopy
import mock
import unittest

from slam.plugins import dynamodb
from .test_deploy import config as deploy_config

config = deepcopy(deploy_config)
config.update({'dynamodb_tables': dynamodb.init.func(config, 't1,t2')[1]})


class DynamoDBTests(unittest.TestCase):
    def test_init(self):
        header, plugin_config = dynamodb.init.func(config=deploy_config,
                                                   dynamodb_tables='a,b ,c, d')
        for table in ['a', 'b', 'c', 'd']:
            self.assertIn(table, plugin_config)
            self.assertEqual(plugin_config[table], {
                'attributes': {'id': 'S'},
                'key': 'id',
                'read_throughput': 1,
                'write_throughput': 1
            })

    def test_policies(self):
        self.assertEqual(dynamodb._get_dynamodb_policies({}), [])
        policies = dynamodb._get_dynamodb_policies(config)
        self.assertEqual(len(policies), 1)
        statement = policies[0]['PolicyDocument']['Statement'][0]
        self.assertEqual(
            statement['Action'],
            ['dynamodb:DeleteItem',
             'dynamodb:GetItem',
             'dynamodb:PutItem',
             'dynamodb:Query',
             'dynamodb:Scan',
             'dynamodb:UpdateItem',
             'dynamodb:DescribeTable'])
        self.assertEqual(len(statement['Resource']), 6)  # 2 tables x 3 stages
        tables = [r['Fn::Join'][1][5]['Ref'] for r in statement['Resource']]
        self.assertEqual(set(tables), {'DevT1DynamoDBTable',
                                       'DevT2DynamoDBTable',
                                       'StagingT1DynamoDBTable',
                                       'StagingT2DynamoDBTable',
                                       'ProdT1DynamoDBTable',
                                       'ProdT2DynamoDBTable'})

    def test_key_schema(self):
        self.assertEqual(dynamodb._get_dynamodb_key_schema('foo'),
                         [{'AttributeName': 'foo', 'KeyType': 'HASH'}])
        self.assertEqual(dynamodb._get_dynamodb_key_schema(['foo', 'bar']),
                         [{'AttributeName': 'foo', 'KeyType': 'HASH'},
                          {'AttributeName': 'bar', 'KeyType': 'RANGE'}])

    def test_index_projection(self):
        self.assertEqual(dynamodb._get_dynamodb_projection(None),
                         {'ProjectionType': 'KEYS_ONLY'})
        self.assertEqual(dynamodb._get_dynamodb_projection([]),
                         {'ProjectionType': 'KEYS_ONLY'})
        self.assertEqual(dynamodb._get_dynamodb_projection('all'),
                         {'ProjectionType': 'ALL'})
        self.assertEqual(dynamodb._get_dynamodb_projection(['foo', 'bar']),
                         {'ProjectionType': 'INCLUDE',
                          'NonKeyAttributes': ['foo', 'bar']})

    @mock.patch('slam.plugins.dynamodb._get_dynamodb_key_schema',
                return_value='key-schema')
    def test_table_schema(self, *args):
        cfg = deepcopy(config)
        cfg['dynamodb_tables']['t1']['attributes'] = {'id': 'S', 'name': 'S',
                                                      'age': 'N'}
        cfg['dynamodb_tables']['t1']['read_throughput'] = 2
        cfg['dynamodb_tables']['t1']['write_throughput'] = 4
        table = dynamodb._get_table_resource(cfg, 'dev', 't1')
        self.assertEqual(table['Properties']['TableName'], 'dev.t1')
        self.assertEqual(len(table['Properties']['AttributeDefinitions']), 3)
        for attr in table['Properties']['AttributeDefinitions']:
            self.assertIn(attr['AttributeName'],
                          cfg['dynamodb_tables']['t1']['attributes'])
            self.assertEqual(attr['AttributeType'],
                             cfg['dynamodb_tables']['t1']['attributes']
                             [attr['AttributeName']])
        self.assertEqual(table['Properties']['ProvisionedThroughput'],
                         {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 4})
        self.assertEqual(table['Properties']['KeySchema'], 'key-schema')

    @mock.patch('slam.plugins.dynamodb._get_dynamodb_projection',
                return_value='projection')
    @mock.patch('slam.plugins.dynamodb._get_dynamodb_key_schema',
                return_value='key-schema')
    def test_local_indexes(self, _get_dynamodb_key_schema,
                           _get_dynamodb_projection):
        cfg = deepcopy(config)
        cfg['dynamodb_tables']['t1']['attributes'] = {'id': 'S', 'name': 'S'}
        cfg['dynamodb_tables']['t1']['local_secondary_indexes'] = {
            'index1': {'key': 'foo', 'projection': 'bar'}
        }
        table = dynamodb._get_table_resource(cfg, 'dev', 't1')
        self.assertEqual(table['Properties']['LocalSecondaryIndexes'], {
            'IndexName': 'index1',
            'KeySchema': 'key-schema',
            'Projection': 'projection'
        })
        _get_dynamodb_key_schema.assert_any_call('foo')
        _get_dynamodb_projection.assert_called_once_with('bar')

    @mock.patch('slam.plugins.dynamodb._get_dynamodb_projection',
                return_value='projection')
    @mock.patch('slam.plugins.dynamodb._get_dynamodb_key_schema',
                return_value='key-schema')
    def test_global_indexes(self, _get_dynamodb_key_schema,
                            _get_dynamodb_projection):
        cfg = deepcopy(config)
        cfg['dynamodb_tables']['t1']['attributes'] = {'id': 'S', 'name': 'S'}
        cfg['dynamodb_tables']['t1']['global_secondary_indexes'] = {
            'index2': {'key': 'foo', 'projection': 'bar', 'read_throughput': 2,
                       'write_throughput': 4}
        }
        table = dynamodb._get_table_resource(cfg, 'dev', 't1')
        self.assertEqual(table['Properties']['GlobalSecondaryIndexes'], {
            'IndexName': 'index2',
            'KeySchema': 'key-schema',
            'Projection': 'projection',
            'ProvisionedThroughput': {'ReadCapacityUnits': 2,
                                      'WriteCapacityUnits': 4}
        })
        _get_dynamodb_key_schema.assert_any_call('foo')
        _get_dynamodb_projection.assert_called_once_with('bar')

    @mock.patch('slam.plugins.dynamodb._get_dynamodb_policies',
                return_value=['policies'])
    @mock.patch('slam.plugins.dynamodb._get_table_resource',
                return_value='resource')
    def test_cfn_template(self, _get_table_resource, _get_dynamodb_policies):
        tpl = dynamodb.cfn_template(config, {'Resources': {
            'FunctionExecutionRole': {'Properties': {'Policies': ['foo']}}}})
        self.assertEqual(tpl, {'Resources': {
            'DevT1DynamoDBTable': 'resource',
            'DevT2DynamoDBTable': 'resource',
            'StagingT1DynamoDBTable': 'resource',
            'StagingT2DynamoDBTable': 'resource',
            'ProdT1DynamoDBTable': 'resource',
            'ProdT2DynamoDBTable': 'resource',
            'FunctionExecutionRole': {
                'Properties': {'Policies': ['foo', 'policies']}}
        }})
