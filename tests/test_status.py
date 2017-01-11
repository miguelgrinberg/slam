import mock
import unittest

from slam import cli
from .test_deploy import config


class StatusTests(unittest.TestCase):
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_status(self, _load_config, _print_status):
        cli.main(['status'])
        _print_status.assert_called_once_with(config)
