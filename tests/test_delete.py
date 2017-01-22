import mock
import unittest

import botocore

from slam import cli
from .test_deploy import config, describe_stacks_response


class DeleteTests(unittest.TestCase):
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        cli.main(['delete'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_cfn.delete_stack.assert_called_once_with(StackName='foo')
        mock_cfn.get_waiter.assert_called_once_with('stack_delete_complete')
        mock_cfn.get_waiter().wait.assert_called_once_with(StackName='foo')
        mock_logs.delete_log_group.assert_any_call(
            logGroupName='/aws/lambda/foo')
        mock_logs.delete_log_group.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/dev')
        mock_logs.delete_log_group.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/staging')
        mock_logs.delete_log_group.assert_any_call(
            logGroupName='API-Gateway-Execution-Logs_123abc/prod')
        mock_s3.delete_object.assert_called_once_with(Bucket='bucket',
                                                      Key='lambda-old.zip')
        mock_s3.delete_bucket(Bucket='bucket')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete_no_logs(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        cli.main(['delete', '--no-logs'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_cfn.delete_stack.assert_called_once_with(StackName='foo')
        mock_cfn.get_waiter.assert_called_once_with('stack_delete_complete')
        mock_cfn.get_waiter().wait.assert_called_once_with(StackName='foo')
        mock_logs.delete_log_group.assert_not_called()
        mock_s3.delete_object.assert_called_once_with(Bucket='bucket',
                                                      Key='lambda-old.zip')
        mock_s3.delete_bucket(Bucket='bucket')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete_not_deployed(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        self.assertRaises(RuntimeError, cli.main, ['delete'])

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete_fail_log_group(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_logs.delete_log_group.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        cli.main(['delete'])  # should still work in spite of error

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete_fail_s3_file(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_s3.delete_object.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        cli.main(['delete'])  # should still work in spite of error

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_delete_fail_s3_bucket(self, _load_config, client):
        mock_s3 = mock.MagicMock()
        mock_logs = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_s3.delete_bucket.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn, mock_logs]

        cli.main(['delete'])  # should still work in spite of error
