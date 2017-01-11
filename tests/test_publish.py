import mock
import unittest

import botocore

from slam import cli
from .test_deploy import config, describe_stacks_response


class PublishTests(unittest.TestCase):
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish(self, _load_config, client, _get_cfn_template,
                     _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['publish', 'prod'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        _get_cfn_template.assert_called_once_with(config, custom_template=None)
        mock_lmb.publish_version.assert_called_once_with(
            FunctionName='arn.foo')
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda-old.zip'},
                {'ParameterKey': 'LambdaTimeout', 'ParameterValue': '1'},
                {'ParameterKey': 'LambdaMemorySize', 'ParameterValue': '128'},
                {'ParameterKey': 'APIName', 'ParameterValue': 'foo'},
                {'ParameterKey': 'APIDescription', 'ParameterValue': 'bar'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '3'},
                {'ParameterKey': 'StagingVersion', 'ParameterValue': '1'}
            ],
            Capabilities=['CAPABILITY_IAM'])
        mock_cfn.get_waiter.assert_called_once_with('stack_update_complete')
        mock_cfn.get_waiter().wait.assert_called_once_with(StackName='foo')
        _print_status.assert_called_once_with(config)

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_invalid_version(self, _load_config, client,
                                     _get_cfn_template, _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(ValueError, cli.main, ['publish', 'prod',
                                                 '--version', 'prod'])
        self.assertRaises(ValueError, cli.main, ['publish', 'prod',
                                                 '--version', 'badstage'])

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_not_deployed(self, _load_config, client,
                                  _get_cfn_template, _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(RuntimeError, cli.main, ['publish', 'prod'])

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_version_number(self, _load_config, client,
                                    _get_cfn_template, _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['publish', 'prod', '--version', '42'])
        mock_lmb.publish_version.assert_not_called()
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda-old.zip'},
                {'ParameterKey': 'LambdaTimeout', 'ParameterValue': '1'},
                {'ParameterKey': 'LambdaMemorySize', 'ParameterValue': '128'},
                {'ParameterKey': 'APIName', 'ParameterValue': 'foo'},
                {'ParameterKey': 'APIDescription', 'ParameterValue': 'bar'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '42'},
                {'ParameterKey': 'StagingVersion', 'ParameterValue': '1'}
            ],
            Capabilities=['CAPABILITY_IAM'])

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_version_stage(self, _load_config, client,
                                   _get_cfn_template, _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['publish', 'prod', '--version', 'staging'])
        mock_lmb.publish_version.assert_not_called()
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda-old.zip'},
                {'ParameterKey': 'LambdaTimeout', 'ParameterValue': '1'},
                {'ParameterKey': 'LambdaMemorySize', 'ParameterValue': '128'},
                {'ParameterKey': 'APIName', 'ParameterValue': 'foo'},
                {'ParameterKey': 'APIDescription', 'ParameterValue': 'bar'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '1'},
                {'ParameterKey': 'StagingVersion', 'ParameterValue': '1'}
            ],
            Capabilities=['CAPABILITY_IAM'])

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_version_dev(self, _load_config, client, _get_cfn_template,
                                 _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['publish', 'dev', '--version', '42'])
        mock_lmb.publish_version.assert_not_called()
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda-old.zip'},
                {'ParameterKey': 'LambdaTimeout', 'ParameterValue': '1'},
                {'ParameterKey': 'LambdaMemorySize', 'ParameterValue': '128'},
                {'ParameterKey': 'APIName', 'ParameterValue': 'foo'},
                {'ParameterKey': 'APIDescription', 'ParameterValue': 'bar'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '42'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '2'},
                {'ParameterKey': 'StagingVersion', 'ParameterValue': '1'}
            ],
            Capabilities=['CAPABILITY_IAM'])

    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli._get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_publish_fail(self, _load_config, client, _get_cfn_template,
                          _print_status):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_cfn.get_waiter().wait.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        mock_lmb.publish_version.return_value = {'Version': '3'}
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(botocore.exceptions.ClientError, cli.main,
                          ['publish', 'prod'])
