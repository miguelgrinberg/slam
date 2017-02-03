from copy import deepcopy
import mock
import unittest

from slam.plugins import wsgi
from .test_deploy import config as deploy_config

config = deepcopy(deploy_config)
config.update({'wsgi': wsgi.init.func(config, True, False)})


class WSGITests(unittest.TestCase):
    def test_init(self):
        plugin_config = wsgi.init.func(config=deploy_config, wsgi=True,
                                       no_api_gateway=False)
        self.assertEqual(plugin_config['deploy_api_gateway'], True)
        self.assertEqual(plugin_config['log_stages'], ['dev'])

    def test_wsgi_resources(self):
        res = wsgi._get_wsgi_resources(config)
        self.assertIn('Api', res)
        self.assertIn('ApiCloudWatchRole', res)
        self.assertIn('ApiAccount', res)
        self.assertIn('DevApiDeployment', res)
        self.assertIn('StagingApiDeployment', res)
        self.assertIn('ProdApiDeployment', res)
        self.assertIn('DevApiLambdaPermission', res)
        self.assertIn('StagingApiLambdaPermission', res)
        self.assertIn('ProdApiLambdaPermission', res)
        self.assertEqual(
            res['DevApiDeployment']['Properties']['StageDescription']
            ['MethodSettings'][0]['LoggingLevel'], 'INFO')
        self.assertEqual(
            res['StagingApiDeployment']['Properties']['StageDescription']
            ['MethodSettings'][0]['LoggingLevel'], 'ERROR')
        self.assertEqual(
            res['ProdApiDeployment']['Properties']['StageDescription']
            ['MethodSettings'][0]['LoggingLevel'], 'ERROR')

    def test_wsgi_outputs(self):
        outputs = wsgi._get_wsgi_outputs(config)
        self.assertIn('DevEndpoint', outputs)
        self.assertIn('StagingEndpoint', outputs)
        self.assertIn('ProdEndpoint', outputs)

    @mock.patch('slam.plugins.wsgi._get_wsgi_outputs',
                return_value={'o': 'p'})
    @mock.patch('slam.plugins.wsgi._get_wsgi_resources',
                return_value={'r': 's', 't': 'u'})
    def test_cfn_template(self, _get_wsgi_resources, _get_wsgi_outputs):
        tpl = {'Resources': {'foo': 'bar'}, 'Outputs': {'output': 'value'}}
        tpl = wsgi.cfn_template(config, tpl)
        self.assertEqual(tpl, {
            'Resources': {'foo': 'bar', 'r': 's', 't': 'u'},
            'Outputs': {'output': 'value', 'o': 'p'}
        })

    def test_no_api_gateway(self):
        tpl = wsgi.cfn_template({'wsgi': {'deploy_api_gateway': False}}, {})
        self.assertEqual(tpl, {})
