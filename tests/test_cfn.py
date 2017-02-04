from copy import deepcopy
import mock
import unittest

from slam import cfn
from .test_deploy import config


class CloudformationTests(unittest.TestCase):
    def test_parameters(self):
        params = cfn._get_cfn_parameters(config)
        for param in ['LambdaS3Bucket', 'LambdaS3Key', 'DevVersion',
                      'StagingVersion', 'ProdVersion']:
            self.assertIn(param, params)

    def test_resources(self):
        cfg = deepcopy(config)
        cfg['aws']['cfn_resources'] = {'foo': 'bar'}
        resources = cfn._get_cfn_resources(cfg)
        for resource in ['FunctionExecutionRole', 'Function',
                         'DevFunctionAlias', 'StagingFunctionAlias',
                         'ProdFunctionAlias', 'foo']:
            self.assertIn(resource, resources)
        self.assertEqual(resources['Function']['Properties']['Timeout'], 7)
        self.assertEqual(resources['Function']['Properties']['MemorySize'],
                         512)
        self.assertNotIn('VpcConfig', resources['Function']['Properties'])
        self.assertEqual(
            resources['DevFunctionAlias']['Properties']['FunctionVersion'],
            {'Ref': 'DevVersion'})
        self.assertEqual(
            resources['StagingFunctionAlias']['Properties']['FunctionVersion'],
            {'Ref': 'StagingVersion'})
        self.assertEqual(
            resources['ProdFunctionAlias']['Properties']['FunctionVersion'],
            {'Ref': 'ProdVersion'})
        self.assertEqual(resources['foo'], 'bar')

    def test_resources_vpc(self):
        vpc_config = deepcopy(config)
        vpc_config['aws']['lambda_security_groups'] = ['sg1', 'sg2']
        vpc_config['aws']['lambda_subnet_ids'] = ['foo', 'bar']
        resources = cfn._get_cfn_resources(vpc_config)
        for resource in ['FunctionExecutionRole', 'Function',
                         'DevFunctionAlias', 'StagingFunctionAlias',
                         'ProdFunctionAlias']:
            self.assertIn(resource, resources)
        self.assertEqual(resources['Function']['Properties']['VpcConfig'],
                         {'SecurityGroupIds': ['sg1', 'sg2'],
                          'SubnetIds': ['foo', 'bar']})

    def test_resources_policies(self):
        vpc_config = deepcopy(config)
        vpc_config['aws']['lambda_managed_policies'] = ['arn:foo', 'bar']
        vpc_config['aws']['lambda_inline_policies'] = [{'foo': 'bar'}]
        resources = cfn._get_cfn_resources(vpc_config)
        for resource in ['FunctionExecutionRole', 'Function',
                         'DevFunctionAlias', 'StagingFunctionAlias',
                         'ProdFunctionAlias']:
            self.assertIn(resource, resources)
        self.assertEqual(
            resources['FunctionExecutionRole']['Properties']
            ['ManagedPolicyArns'],
            ['arn:aws:iam::aws:policy/service-role/'
             'AWSLambdaBasicExecutionRole',
             'arn:foo', 'arn:aws:iam::aws:policy/service-role/bar'])
        self.assertEqual(
            resources['FunctionExecutionRole']['Properties']['Policies'],
            [{'foo': 'bar'}])

    def test_outputs(self):
        cfg = deepcopy(config)
        cfg['aws']['cfn_outputs'] = {'foo': 'bar'}
        outputs = cfn._get_cfn_outputs(cfg)
        for output in ['FunctionArn', 'foo']:
            self.assertIn(output, outputs)
        self.assertEqual(outputs['foo'], 'bar')

    @mock.patch('slam.cfn._get_cfn_outputs', return_value='baz')
    @mock.patch('slam.cfn._get_cfn_resources', return_value='bar')
    @mock.patch('slam.cfn._get_cfn_parameters', return_value='foo')
    def test_cfn_template(self, params, resources, outputs):
        tpl = cfn.get_cfn_template(config)
        params.assert_called_once_with(config)
        resources.assert_called_once_with(config)
        outputs.assert_called_once_with(config)
        self.assertEqual(tpl, ('{"AWSTemplateFormatVersion": "2010-09-09", '
                               '"Parameters": "foo", "Resources": "bar", '
                               '"Outputs": "baz"}'))

    @mock.patch('slam.cfn._get_cfn_outputs', return_value='baz')
    @mock.patch('slam.cfn._get_cfn_resources', return_value='bar')
    @mock.patch('slam.cfn._get_cfn_parameters', return_value='foo')
    def test_cfn_template_pretty(self, params, resources, outputs):
        tpl = cfn.get_cfn_template(config, pretty=True)
        params.assert_called_once_with(config)
        resources.assert_called_once_with(config)
        outputs.assert_called_once_with(config)
        self.assertEqual(
            tpl, ('{\n'
                  '    "AWSTemplateFormatVersion": "2010-09-09",\n'
                  '    "Parameters": "foo",\n'
                  '    "Resources": "bar",\n'
                  '    "Outputs": "baz"\n'
                  '}'))
