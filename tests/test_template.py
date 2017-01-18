import mock
import unittest

from slam import cli
from .test_deploy import config


class TemplateTests(unittest.TestCase):
    @mock.patch('slam.cli.get_cfn_template')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_template(self, _load_config, get_cfn_template):
        cli.main(['template'])
        get_cfn_template.assert_called_once_with(config, pretty=True)
