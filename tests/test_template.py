import mock
import unittest

from slam import cli
from .test_deploy import config


class TemplateTests(unittest.TestCase):
    @mock.patch('slam.cli._get_cfn_template')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_template(self, _load_config, _get_cfn_template):
        cli.main(['template'])
        _get_cfn_template.assert_called_once_with(config, raw=False)

    @mock.patch('slam.cli._get_cfn_template')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_template_raw(self, _load_config, _get_cfn_template):
        cli.main(['template', '--raw'])
        _get_cfn_template.assert_called_once_with(config, raw=True)
