import os
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
            cfg = yaml.load(f)
        self.assertEqual(cfg['type'], 'wsgi')
        self.assertEqual(cfg['wsgi']['module'], 'app_module')
        self.assertEqual(cfg['wsgi']['app'], 'app')
        self.assertEqual(cfg['devstage'], 'dev')
        self.assertEqual(cfg['stage_environments'], {'dev': None})
        self.assertEqual(cfg['name'], 'app-module')
        self.assertEqual(cfg['aws']['s3_bucket'], 'app-module')
        self.assertEqual(cfg['requirements'], 'requirements.txt')

    def test_init_with_name(self):
        cli.main(['init', '--name', 'foo-bar', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f)
        self.assertEqual(cfg['wsgi']['module'], 'app_module')
        self.assertEqual(cfg['wsgi']['app'], 'app')
        self.assertEqual(cfg['name'], 'foo-bar')
        self.assertEqual(cfg['aws']['s3_bucket'], 'foo-bar')

    def test_init_with_bucket(self):
        cli.main(['init', '--bucket', 'foo-bar', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f)
        self.assertEqual(cfg['wsgi']['module'], 'app_module')
        self.assertEqual(cfg['wsgi']['app'], 'app')
        self.assertEqual(cfg['name'], 'app-module')
        self.assertEqual(cfg['aws']['s3_bucket'], 'foo-bar')

    def test_init_with_requirements(self):
        cli.main(['init', '--requirements', 'foo.txt', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f)
        self.assertEqual(cfg['requirements'], 'foo.txt')

    def test_init_with_stages(self):
        cli.main(['init', '--stages', 'd,s, p', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f)
        self.assertEqual(cfg['devstage'], 'd')
        self.assertEqual(cfg['stage_environments'], {'d': None,
                                                     's': None,
                                                     'p': None})

    def test_init_with_tables(self):
        cli.main(['init', '--dynamodb-tables', 'a,b, c', 'app_module:app'])
        with open('slam.yaml') as f:
            cfg = yaml.load(f)
        t = {'attributes': {'id': 'S'}, 'key': 'id',
             'provisioned_throughput': [1, 1]}
        self.assertEqual(cfg['aws']['dynamodb_tables'],
                         {'a': t, 'b': t, 'c': t})

    def test_init_with_invalid_name(self):
        self.assertRaises(ValueError, cli.main,
                          ['init', '--name', 'foo_bar', 'app_module:app'])

    def test_init_with_existing_config(self):
        with open('slam1.yaml', 'wt') as f:
            f.write('foo')
        self.assertRaises(
            RuntimeError, cli.main,
            ['--config-file', 'slam1.yaml', 'init', 'app_module:app'])
