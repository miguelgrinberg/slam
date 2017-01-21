import mock
import sys
import unittest

import boto3
import botocore

from slam import cfn
from slam import cli

BUILTIN = '__builtin__'
if sys.version_info >= (3, 0):
    BUILTIN = 'builtins'

config = {
    'name': 'foo',
    'description': 'bar',
    'stage_environments': {'dev': {}, 'prod': {}, 'staging': {}},
    'environment': {'abc': 'def'},
    'devstage': 'dev',
    'aws': {'s3_bucket': 'bucket',
            'lambda_timeout': 1,
            'lambda_memory': 128}
}

describe_stacks_response = {'Stacks': [{
    'Parameters': [
        {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
        {'ParameterKey': 'LambdaS3Key',
         'ParameterValue': 'lambda-old.zip'},
        {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
        {'ParameterKey': 'ProdVersion', 'ParameterValue': '2'},
        {'ParameterKey': 'StagingVersion',
         'ParameterValue': '1'}
    ],
    'Outputs': [
        {'OutputKey': 'FunctionArn', 'OutputValue': 'arn:lambda:foo'},
        {'OutputKey': 'DevEndpoint', 'OutputValue': 'https://a.com'},
        {'OutputKey': 'ProdEndpoint', 'OutputValue': 'https://b.com'},
        {'OutputKey': 'StagingEndpoint',
         'OutputValue': 'https://c.com'},
    ]
}]}


class DeployTests(unittest.TestCase):
    def test_get_from_stack(self):
        stack = {
            'Parameters': [
                {'ParameterKey': 'foo',
                 'ParameterValue': 'bar'},
                {'ParameterKey': 'key',
                 'ParameterValue': 'value'}
            ],
            'Outputs': [
                {'OutputKey': 'foo',
                 'OutputValue': 'bar'},
                {'OutputKey': 'key',
                 'OutputValue': 'value'}
            ]
        }
        self.assertEqual(cli._get_from_stack(stack, 'Parameter', 'foo'), 'bar')
        self.assertEqual(cli._get_from_stack(stack, 'Parameter', 'key'),
                         'value')
        self.assertEqual(cli._get_from_stack(stack, 'Parameter', 'x'), None)
        self.assertEqual(cli._get_from_stack(stack, 'Output', 'foo'), 'bar')
        self.assertEqual(cli._get_from_stack(stack, 'Output', 'key'),
                         'value')
        self.assertEqual(cli._get_from_stack(stack, 'Output', 'x'), None)
        self.assertRaises(ValueError, cli._get_from_stack, stack, 'Foo', 'bar')

    def test_get_template(self):
        tpl = cfn.get_cfn_template(config)
        self.assertTrue(tpl.startswith(
            '{"AWSTemplateFormatVersion": "2010-09-09"'))
        try:
            client = boto3.client('cloudformation')
        except botocore.exceptions.BotoCoreError:
            pass
        else:
            client.validate_template(TemplateBody=tpl)
        # TODO: find an offline cloudformation validator that can be used here
        # without having to have aws creds

    @mock.patch('slam.cli.boto3.client')
    @mock.patch(BUILTIN + '.print')
    def test_print_status(self, mock_print, client):
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = {'Stacks': [{
            'Outputs': [
                {'OutputKey': 'FunctionArn', 'OutputValue': 'arn:lambda:foo'},
                {'OutputKey': 'DevEndpoint', 'OutputValue': 'https://a.com'},
                {'OutputKey': 'ProdEndpoint', 'OutputValue': 'https://b.com'},
                {'OutputKey': 'StagingEndpoint',
                 'OutputValue': 'https://c.com'},
            ]
        }]}
        mock_lmb = mock.MagicMock()
        mock_lmb.get_function.side_effect = [
            {'Configuration': {'Version': '$LATEST'}},
            {'Configuration': {'Version': '23'}},
            {'Configuration': {'Version': '$LATEST'}},
        ]
        client.side_effect = [mock_cfn, mock_lmb]

        cli._print_status(config)
        output = ''.join([c[0][0] + '\n' for c in mock_print.call_args_list])
        self.assertEqual(output, ('foo is deployed!\n'
                                  '  dev:$LATEST: https://a.com\n'
                                  '  prod:23: https://b.com\n'
                                  '  staging: https://c.com\n'))

    @mock.patch('slam.cli.boto3.client')
    @mock.patch(BUILTIN + '.print')
    def test_print_status_not_deployed(self, mock_print, client):
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        mock_lmb = mock.MagicMock()
        mock_lmb.get_function.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_cfn, mock_lmb]
        cli._print_status(config)
        output = ''.join([c[0][0] + '\n' for c in mock_print.call_args_list])
        self.assertEqual(output, 'foo has not been deployed yet.\n')

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_first(self, _load_config, client, _get_aws_region, _build,
                          _ensure_bucket_exists, get_cfn_template,
                          _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        _build.assert_called_once_with(config, rebuild_deps=False)
        _ensure_bucket_exists.assert_called_once_with(mock_s3, 'bucket',
                                                      'us-east-1')
        mock_s3.upload_file.assert_called_with('lambda.zip', 'bucket',
                                               'lambda.zip')
        remove.assert_called_once_with('lambda.zip')
        mock_cfn.create_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda.zip'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'StagingVersion',
                 'ParameterValue': '$LATEST'}],
            Capabilities=['CAPABILITY_IAM'])
        mock_cfn.get_waiter.assert_called_once_with('stack_create_complete')
        mock_cfn.get_waiter().wait.assert_called_once_with(StackName='foo')
        _print_status.assert_called_once_with(config)

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_update(self, _load_config, client, _get_aws_region, _build,
                           _ensure_bucket_exists, get_cfn_template,
                           _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        _build.assert_called_once_with(config, rebuild_deps=False)
        _ensure_bucket_exists.assert_called_once_with(mock_s3, 'bucket',
                                                      'us-east-1')
        mock_s3.upload_file.assert_called_with('lambda.zip', 'bucket',
                                               'lambda.zip')
        remove.assert_called_once_with('lambda.zip')
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda.zip'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '2'},
                {'ParameterKey': 'StagingVersion',
                 'ParameterValue': '1'}],
            Capabilities=['CAPABILITY_IAM'])
        mock_s3.delete_object(Bucket='bucket', Key='lambda-old.zip')
        mock_cfn.get_waiter.assert_called_once_with('stack_update_complete')
        mock_cfn.get_waiter().wait.assert_called_once_with(StackName='foo')
        _print_status.assert_called_once_with(config)

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_with_package(self, _load_config, client, _get_aws_region,
                                 _build, _ensure_bucket_exists,
                                 get_cfn_template, _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy', '--lambda-package', 'my-lambda.zip'])
        _build.assert_not_called()
        mock_s3.upload_file.assert_called_with('my-lambda.zip', 'bucket',
                                               'my-lambda.zip')
        try:
            remove.assert_called_once_with('my-lambda.zip')
        except AssertionError:
            pass
        else:
            raise AssertionError('file should not have been deleted')

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_no_lambda(self, _load_config, client, _get_aws_region,
                              _build, _ensure_bucket_exists, get_cfn_template,
                              _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy', '--no-lambda'])
        _build.assert_not_called()
        mock_s3.upload_file.assert_not_called()
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda-old.zip'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '2'},
                {'ParameterKey': 'StagingVersion',
                 'ParameterValue': '1'}],
            Capabilities=['CAPABILITY_IAM'])
        print(mock_s3.delete_object.call_args_list)
        mock_s3.delete_object.assert_not_called()

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_rebuild(self, _load_config, client, _get_aws_region,
                            _build, _ensure_bucket_exists, get_cfn_template,
                            _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy', '--rebuild-deps'])
        _build.assert_called_once_with(config, rebuild_deps=True)

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_stage(self, _load_config, client, _get_aws_region, _build,
                          _ensure_bucket_exists, get_cfn_template,
                          _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        client.side_effect = [mock_s3, mock_cfn]

        cli.main(['deploy', '--stage', 'staging'])
        mock_cfn.update_stack.assert_called_once_with(
            StackName='foo', TemplateBody='cfn-template',
            Parameters=[
                {'ParameterKey': 'LambdaS3Bucket', 'ParameterValue': 'bucket'},
                {'ParameterKey': 'LambdaS3Key',
                 'ParameterValue': 'lambda.zip'},
                {'ParameterKey': 'DevVersion', 'ParameterValue': '$LATEST'},
                {'ParameterKey': 'ProdVersion', 'ParameterValue': '2'},
                {'ParameterKey': 'StagingVersion',
                 'ParameterValue': '$LATEST'}],
            Capabilities=['CAPABILITY_IAM'])

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_fail(self, _load_config, client, _get_aws_region, _build,
                         _ensure_bucket_exists, get_cfn_template,
                         _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        mock_cfn.get_waiter().wait.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn]

        self.assertRaises(botocore.exceptions.ClientError, cli.main,
                          ['deploy'])
        mock_s3.delete_object.assert_called_once_with(Bucket='bucket',
                                                      Key='lambda.zip')

    @mock.patch('slam.cli.os.remove')
    @mock.patch('slam.cli._print_status')
    @mock.patch('slam.cli.get_cfn_template', return_value='cfn-template')
    @mock.patch('slam.cli._ensure_bucket_exists')
    @mock.patch('slam.cli._build', return_value='lambda.zip')
    @mock.patch('slam.cli._get_aws_region', return_value='us-east-1')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_deploy_fail_no_lambda(self, _load_config, client, _get_aws_region,
                                   _build, _ensure_bucket_exists,
                                   get_cfn_template, _print_status, remove):
        mock_s3 = mock.MagicMock()
        mock_cfn = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_cfn.get_waiter().wait.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_s3, mock_cfn]

        self.assertRaises(botocore.exceptions.ClientError, cli.main,
                          ['deploy', '--no-lambda'])
        mock_s3.delete_object.assert_not_called()
