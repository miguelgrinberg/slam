import mock
import os
import sys
import unittest

import yaml

from slam import cli


class InitTests(unittest.TestCase):
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

    def test_init_with_defaults(self):
        cli.main(['init', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['function']['module'], 'app_module')
        self.assertEqual(cfg['function']['app'], 'app')
        self.assertEqual(cfg['devstage'], 'dev')
        self.assertEqual(cfg['stage_environments'], {'dev': None})
        self.assertEqual(cfg['name'], 'app-module')
        self.assertTrue(cfg['aws']['s3_bucket'].startswith('app-module-'))
        self.assertEqual(cfg['requirements'], 'requirements.txt')
        if sys.version_info[0] == 2:
            self.assertEqual(cfg['aws']['lambda_runtime'], 'python2.7')
        else:
            self.assertEqual(cfg['aws']['lambda_runtime'], 'python3.6')

    def test_init_with_name(self):
        cli.main(['init', '--name', 'foo-bar', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['function']['module'], 'app_module')
        self.assertEqual(cfg['function']['app'], 'app')
        self.assertEqual(cfg['name'], 'foo-bar')
        self.assertTrue(cfg['aws']['s3_bucket'].startswith('foo-bar-'))

    def test_init_with_bucket(self):
        cli.main(['init', '--bucket', 'foo-bar', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['function']['module'], 'app_module')
        self.assertEqual(cfg['function']['app'], 'app')
        self.assertEqual(cfg['name'], 'app-module')
        self.assertEqual(cfg['aws']['s3_bucket'], 'foo-bar')

    def test_init_with_requirements(self):
        cli.main(['init', '--requirements', 'foo.txt', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['requirements'], 'foo.txt')

    def test_init_with_stages(self):
        cli.main(['init', '--stages', 'd,s, p', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['devstage'], 'd')
        self.assertEqual(cfg['stage_environments'],
                         {'d': None, 's': None, 'p': None})

    def test_init_with_runtime(self):
        cli.main(['init', '--runtime', 'foo', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.assertEqual(cfg['aws']['lambda_runtime'], 'foo')

    def test_init_with_tables(self):
        cli.main(['init', '--dynamodb-tables', 'a,b, c', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        t = {'attributes': {'id': 'S'}, 'key': 'id',
             'read_throughput': 1, 'write_throughput': 1}
        self.assertEqual(cfg['dynamodb_tables'], {'a': t, 'b': t, 'c': t})

    def test_init_with_invalid_name(self):
        self.assertRaises(ValueError, cli.main,
                          ['init', '--name', 'foo_bar', 'app_module:app'])

    def test_init_with_existing_config(self):
        with open('slam1.yaml', 'wt') as f:
            f.write('foo')
        self.assertRaises(
            RuntimeError, cli.main,
            ['--config-file', 'slam1.yaml', 'init', 'app_module:app'])

    def test_load_config(self):
        mock_open = mock.mock_open(
            read_data='---\nfoo: bar\nbaz:\n  - a\n  - b\n')
        with mock.patch('slam.cli.open', mock_open, create=True):
            config = cli._load_config()
        mock_open.assert_called_once_with('slam.yaml')
        self.assertEqual(config, {'foo': 'bar', 'baz': ['a', 'b']})

    def test_load_custom_config(self):
        mock_open = mock.mock_open(
            read_data='---\nfoo: bar\nbaz:\n  - a\n  - b\n')
        with mock.patch('slam.cli.open', mock_open, create=True):
            config = cli._load_config('slam1.yaml')
        mock_open.assert_called_once_with('slam1.yaml')
        self.assertEqual(config, {'foo': 'bar', 'baz': ['a', 'b']})

    def test_load_invalid_config(self):
        self.assertRaises(RuntimeError, cli._load_config, 'bad_file.yaml')
