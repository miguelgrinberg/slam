from io import BytesIO
import json
import mock
import sys
import unittest

import botocore

from slam import cli
from .test_deploy import config, describe_stacks_response

BUILTIN = '__builtin__'
if sys.version_info >= (3, 0):
    BUILTIN = 'builtins'


class InvokeTests(unittest.TestCase):
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_with_args(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 200,
                                        'Payload': BytesIO(b'{"foo":"bar"}')}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke', 'arg=string', 'arg2:=true', 'arg3:=123',
                  'arg4:={"foo":"bar"}'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_lmb.invoke.assert_called_once_with(
            FunctionName='arn:lambda:foo', InvocationType='RequestResponse',
            Payload='{"kwargs": {"arg": "string", "arg2": true, "arg3": 123, '
                    '"arg4": {"foo": "bar"}}}', Qualifier='dev')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_with_stage(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 200,
                                        'Payload': BytesIO(b'{"foo":"bar"}')}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke', '--stage', 'prod'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_lmb.invoke.assert_called_once_with(
            FunctionName='arn:lambda:foo', InvocationType='RequestResponse',
            Payload='{"kwargs": {}}', Qualifier='prod')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_no_args(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 200,
                                        'Payload': BytesIO(b'{"foo":"bar"}')}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_lmb.invoke.assert_called_once_with(
            FunctionName='arn:lambda:foo', InvocationType='RequestResponse',
            Payload='{"kwargs": {}}', Qualifier='dev')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_not_deployed(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.side_effect = \
            botocore.exceptions.ClientError({'Error': {}}, 'operation')
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(RuntimeError, cli.main, ['invoke'])

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_dry_run(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 200,
                                        'Payload': BytesIO(b'{"foo":"bar"}')}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke', '--dry-run'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_lmb.invoke.assert_called_once_with(
            FunctionName='arn:lambda:foo', InvocationType='DryRun',
            Payload='{"kwargs": {}}', Qualifier='dev')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_async(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 202,
                                        'Payload': BytesIO(b'')}
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke', '--async'])
        mock_cfn.describe_stacks.assert_called_once_with(StackName='foo')
        mock_lmb.invoke.assert_called_once_with(
            FunctionName='arn:lambda:foo', InvocationType='Event',
            Payload='{"kwargs": {}}', Qualifier='dev')

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_invalid_arg(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 202,
                                        'Payload': BytesIO(b'')}
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(ValueError, cli.main, ['invoke', 'invalid-argument'])

    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_unexpected_error(self, _load_config, client):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {'StatusCode': 500,
                                        'Payload': BytesIO(b'')}
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(RuntimeError, cli.main, ['invoke'])

    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_error(self, _load_config, client, mock_print):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {
            'StatusCode': 200,
            'FunctionError': 'Unhandled',
            'Payload': BytesIO(json.dumps({
                'stackTrace': [
                    ['file.py', 123, 'module', 'code'],
                    ['file2.py', 456, 'module2', 'code2']
                ],
                'errorMessage': 'foo-error',
                'errorType': 'FooError'
            }).encode('utf-8'))
        }
        client.side_effect = [mock_cfn, mock_lmb]

        cli.main(['invoke'])
        output = ''.join([c[0][0] + '\n' for c in mock_print.call_args_list])
        self.assertEqual(output, 'Traceback (most recent call last):\n'
                                 '  File "file.py", line 123, in module\n'
                                 '    code\n'
                                 '  File "file2.py", line 456, in module2\n'
                                 '    code2\n'
                                 'FooError: foo-error\n')

    @mock.patch(BUILTIN + '.print')
    @mock.patch('slam.cli.boto3.client')
    @mock.patch('slam.cli._load_config', return_value=config)
    def test_invoke_error_no_stack_trace(self, _load_config, client,
                                         mock_print):
        mock_cfn = mock.MagicMock()
        mock_lmb = mock.MagicMock()
        mock_cfn.describe_stacks.return_value = describe_stacks_response
        mock_lmb.invoke.return_value = {
            'StatusCode': 200,
            'FunctionError': 'Unhandled',
            'Payload': BytesIO(json.dumps({}).encode('utf-8'))
        }
        client.side_effect = [mock_cfn, mock_lmb]

        self.assertRaises(RuntimeError, cli.main, ['invoke'])
