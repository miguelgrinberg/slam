from io import BytesIO
import mock
import os
import unittest

import climax
import json
import yaml

from slam import cfn
from slam import cli


class PluginTests(unittest.TestCase):
    def setUp(self):
        try:
            os.remove('slam.yaml')
        except OSError:
            pass

    def tearDown(self):
        try:
            os.remove('slam.yaml')
        except OSError:
            pass
        try:
            os.remove('slam1.yaml')
        except OSError:
            pass

    @mock.patch('slam.cli.pkg_resources.iter_entry_points')
    def test_register_plugins(self, iter_entry_points):

        @climax.command()
        @climax.argument('--foo-option')
        def plugin_init(config, foo_option):
            return {'x': 'y'}

        def plugin_cfn_template(config, template):
            template['Resources']['foo'] = config['foo']
            return template

        plugin_module = mock.MagicMock(spec='init')
        plugin_module.__doc__ = 'test plugin\n'
        plugin_module.init = plugin_init
        plugin_module.cfn_template = plugin_cfn_template
        plugin = mock.MagicMock()
        plugin.name = 'foo'
        plugin.load.return_value = plugin_module
        plugin_without_init = mock.MagicMock()
        plugin_without_init.name = 'bar'
        plugin_without_init.load.return_value = mock.MagicMock(spec=[])
        iter_entry_points.return_value = [plugin, plugin_without_init]
        cli.register_plugins()
        iter_entry_points.assert_called_once_with('slam_plugins')
        self.assertEqual(cli.init._arguments[-1], (('--foo-option',), {}))
        self.assertEqual(cli.init._argnames[-1], 'foo_option')
        self.assertEqual(cli.plugins['foo'], plugin_module)

        cli.main(['init', '--foo-option', 'abc', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = f.read()
        self.assertIn('# test plugin\n# \nfoo:\n  x: y\n', cfg)

        cfg = yaml.load(BytesIO(cfg.encode('utf-8')))
        self.assertEqual(cfg['foo'], {'x': 'y'})

        tpl = cfn.get_cfn_template(cfg)
        tpl = json.loads(tpl)
        self.assertEqual(tpl['Resources']['foo'], {'x': 'y'})
