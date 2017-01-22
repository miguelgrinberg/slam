import mock
import sys
import unittest

import botocore

from slam import cli
from .test_deploy import config, describe_stacks_response

BUILTIN = '__builtin__'
if sys.version_info >= (3, 0):
    BUILTIN = 'builtins'


class LogsTests(unittest.TestCase):
    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.time.time', return_value=1000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_dev_logs(self, _load_config, client, time, mock_print):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': [
                    {'timestamp': 990025, 'message': 'bar'}
                ]
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=940000, interleaved=True)
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/dev',
            startTime=940000, interleaved=True)
        self.assertEqual(mock_print.call_count, 3)
        self.assertIn(' foo', mock_print.call_args_list[0][0][0])
        self.assertIn(' bar', mock_print.call_args_list[1][0][0])
        self.assertIn(' baz', mock_print.call_args_list[2][0][0])

    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.time.time', return_value=1000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_stage_logs(self, _load_config, client, time, mock_print):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[2]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': [
                    {'timestamp': 990025, 'message': 'bar'}
                ]
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--stage', 'prod'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=940000, interleaved=True)
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/prod',
            startTime=940000, interleaved=True)
        self.assertEqual(mock_print.call_count, 2)
        self.assertIn(' foo', mock_print.call_args_list[0][0][0])
        self.assertIn(' bar', mock_print.call_args_list[1][0][0])

    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.time.time', return_value=1000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_no_group(self, _load_config, client, time, mock_print):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            botocore.exceptions.ClientError({'Error': {}}, 'operation'),
            {
                'events': [
                    {'timestamp': 990025, 'message': 'bar'}
                ]
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=940000, interleaved=True)
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/dev',
            startTime=940000, interleaved=True)
        self.assertEqual(mock_print.call_count, 1)
        self.assertIn(' bar', mock_print.call_args_list[0][0][0])

    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.time.time', return_value=1000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_paginated_logs(self, _load_config, client, time, mock_print):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'bar'},
                ],
                'nextToken': 'foo-token'
            },
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990075,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=940000, interleaved=True)
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=990051, interleaved=True,
            nextToken='foo-token')
        self.assertEqual(mock_print.call_count, 3)
        self.assertIn(' foo', mock_print.call_args_list[0][0][0])
        self.assertIn(' bar', mock_print.call_args_list[1][0][0])
        self.assertIn(' baz', mock_print.call_args_list[2][0][0])

    @mock.patch('slam.cli.time.sleep')
    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.time.time', return_value=1000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_tailed_logs(self, _load_config, client, time, mock_print,
                         mock_sleep):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'bar'},
                ],
            },
            {
                'events': []
            },
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990075,
                     'message': 'baz'},
                ]
            },
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990074,
                     'message': 'api'},
                ]
            },
            RuntimeError
        ]
        client.side_effect = [mock_cfn, mock_logs]

        try:
            cli.main(['logs', '--tail'])
        except RuntimeError:
            pass
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=940000, interleaved=True)
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=990051, interleaved=True)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(5)
        self.assertEqual(mock_print.call_count, 4)
        self.assertIn(' foo', mock_print.call_args_list[0][0][0])
        self.assertIn(' bar', mock_print.call_args_list[1][0][0])
        self.assertIn(' api', mock_print.call_args_list[2][0][0])
        self.assertIn(' baz', mock_print.call_args_list[3][0][0])

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_week_logs(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--period', '1w'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=395200000,
            interleaved=True)

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_day_logs(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--period', '2.5d'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=784000000,
            interleaved=True)

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_hour_logs(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--period', '5h'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=982000000,
            interleaved=True)

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_minute_logs(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--period', '10m'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=999400000,
            interleaved=True)

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_second_logs(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.side_effect = [
            {
                'events': [
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[1]', 'timestamp': 990000,
                     'message': 'foo'},
                    {'logStreamName': 'abc[$LATEST]', 'timestamp': 990050,
                     'message': 'baz'},
                ]
            },
            {
                'events': []
            }
        ]
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs', '--period', '6s'])
        mock_logs.filter_log_events.assert_any_call(
            logGroupName='/aws/lambda/foo', startTime=999994000,
            interleaved=True)

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invalid_period_suffix(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.return_value = {
            'events': [
                {'timestamp': 1000, 'message': 'foo'},
                {'timestamp': 1001, 'message': 'bar'},
            ]
        }
        client.side_effect = [mock_cfn, mock_logs]

        self.assertRaises(ValueError, cli.main, ['logs', '--period', '5b'])

    @mock.patch('slam.cli.time.time', return_value=1000000)
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invalid_period_value(self, _load_config, client, time):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.filter_log_events.return_value = {
            'events': [
                {'timestamp': 1000, 'message': 'foo'},
                {'timestamp': 1001, 'message': 'bar'},
            ]
        }
        client.side_effect = [mock_cfn, mock_logs]

        self.assertRaises(ValueError, cli.main, ['logs', '--period', '5ad'])

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_not_deployed(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        mock_logs.filter_log_events.return_value = {
            'events': [
                {'timestamp': 1000, 'message': 'foo'},
                {'timestamp': 1001, 'message': 'bar'},
            ]
        }
        client.side_effect = [mock_cfn, mock_logs]

        cli.main(['logs'])
        mock_logs.filter_log_events.assert_not_called()
