import inspect
import os
import re
import unittest

import mock

from slam import cli


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.config = {'requirements': 'requirements.txt'}

    def test_run_command(self):
        out = cli._run_command('echo test')
        self.assertEqual(out, b'test\n')

    def test_failed_run_command(self):
        self.assertRaises(RuntimeError, cli._run_command, 'false')

    def test_invalid_run_command(self):
        self.assertRaises(RuntimeError, cli._run_command, 'bad_command')

    def test_generate_lambda_handler(self):
        cli._generate_lambda_handler(
            {'function': {'module': 'my_module', 'app': 'my_app'}},
            output='_slam.yaml')
        with open('_slam.yaml') as f:
            handler = f.read()
        os.remove('_slam.yaml')
        self.assertIn('from my_module import my_app', handler)
        self.assertIn(''.join(inspect.getsourcelines(
            cli._run_lambda_function)[0][1:]), handler)

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, False, True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build(self, rmtree, build_package, _run_command,
                   _generate_lambda_handler, mkdir, exists):
        saved_venv = os.environ.get('VIRTUAL_ENV')
        del os.environ['VIRTUAL_ENV']
        pkg = cli._build(self.config)
        if saved_venv:
            os.environ['VIRTUAL_ENV'] = saved_venv
        self.assertIsNotNone(re.match('^lambda_package\\.[0-9]*_[0-9]*\\.zip',
                                      pkg))
        mkdir.assert_called_once_with('.slam')
        _generate_lambda_handler.assert_called_once_with(self.config)
        _run_command.asssert_any_call('virtualenv .slam/venv')
        _run_command.asssert_any_call('.slam/venv/bin/pip install -r '
                                      'requirements.txt')
        build_package.assert_called_once_with(
            '.', 'requirements.txt', virtualenv='.slam/venv',
            extra_files=['.slam/handler.py'],
            ignore=[r'\.slam\/venv\/.*$', r'\.pyc$'], zipfile_name=pkg)
        rmtree.assert_called_once_with('.lambda_uploader_temp')

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, False, True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_from_venv(self, rmtree, build_package, _run_command,
                             _generate_lambda_handler, mkdir, exists):
        # in this test, a venv is active and located in the project's
        # directory. The ignore list for the lambda package should have it.
        saved_venv = os.environ.get('VIRTUAL_ENV')
        os.environ['VIRTUAL_ENV'] = os.path.join(os.path.dirname(__file__),
                                                 'venv')
        pkg = cli._build(self.config)
        if saved_venv:
            os.environ['VIRTUAL_ENV'] = saved_venv
        else:
            del os.environ['VIRTUAL_ENV']
        build_package.assert_called_once_with(
            '.', 'requirements.txt', virtualenv='.slam/venv',
            extra_files=['.slam/handler.py'],
            ignore=[r'\.slam\/venv\/.*$', r'\.pyc$',
                    r'tests\/venv\/.*$'],
            zipfile_name=pkg)

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, False, True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_from_external_venv(self, rmtree, build_package,
                                      _run_command, _generate_lambda_handler,
                                      mkdir, exists):
        # in this test, a venv is active, but it is outside of the project's
        # directory. The ignore list for the lambda build should not change.
        saved_venv = os.environ.get('VIRTUAL_ENV')
        os.environ['VIRTUAL_ENV'] = os.path.join(__file__, '../../../venv')
        pkg = cli._build(self.config)
        if saved_venv:
            os.environ['VIRTUAL_ENV'] = saved_venv
        else:
            del os.environ['VIRTUAL_ENV']
        build_package.assert_called_once_with(
            '.', 'requirements.txt', virtualenv='.slam/venv',
            extra_files=['.slam/handler.py'],
            ignore=[r'\.slam\/venv\/.*$', r'\.pyc$'], zipfile_name=pkg)

    @mock.patch('slam.cli.os.path.exists', side_effect=[True, False, True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_existing_build_dir(self, rmtree, build_package,
                                      _run_command, _generate_lambda_handler,
                                      mkdir, exists):
        # if the .slam directory exists, it should not be created again.
        cli._build(self.config)
        mkdir.assert_not_called()

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, True, False,
                                                        True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_rebuid_deps(self, rmtree, build_package, _run_command,
                               _generate_lambda_handler, mkdir, exists):
        # the .slam/venv directory needs to be removed
        cli._build(self.config, rebuild_deps=True)
        exists.assert_has_calls([mock.call('.slam/venv'),
                                 mock.call('.slam/venv')])
        rmtree.assert_any_call('.slam/venv')

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, False, False,
                                                        True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_rebuid_deps_first_time(
            self, rmtree, build_package, _run_command,
            _generate_lambda_handler, mkdir, exists):
        # a rebuild was requested, but there is no previous build so nothing
        # needs to change
        cli._build(self.config, rebuild_deps=True)
        try:
            rmtree.assert_any_call('.slam/venv')
        except AssertionError:
            pass
        else:
            raise AssertionError('directory should not have been deleted')

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, True, True])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_virtualenv_exists(self, rmtree, build_package, _run_command,
                                     _generate_lambda_handler, mkdir, exists):
        # the .slam/venv virtualenv already exists, should not be created
        cli._build(self.config)
        try:
            _run_command.assert_any_call('virtualenv .slam/venv')
        except AssertionError:
            pass
        else:
            raise AssertionError('venv should not have been created')

    @mock.patch('slam.cli.os.path.exists', side_effect=[False, False, False])
    @mock.patch('slam.cli.os.mkdir')
    @mock.patch('slam.cli._generate_lambda_handler')
    @mock.patch('slam.cli._run_command')
    @mock.patch('slam.cli.build_package')
    @mock.patch('slam.cli.shutil.rmtree')
    def test_build_no_lambda_temp_dir(
            self, rmtree, build_package, _run_command,
            _generate_lambda_handler, mkdir, exists):
        # the lambda uploader temp directory does not exist, should not be
        # deleted
        cli._build(self.config)
        try:
            rmtree.assert_any_call('.lambda_uploader_temp')
        except AssertionError:
            pass
        else:
            raise AssertionError('directory should not have been deleted')

    @mock.patch('slam.cli._load_config', return_value={'requirements': 'r'})
    @mock.patch('slam.cli._build')
    def test_cli_build(self, _build, _load_config):
        cli.main(['build'])
        _build.assert_called_once_with({'requirements': 'r'},
                                       rebuild_deps=False)

    @mock.patch('slam.cli._load_config', return_value={'requirements': 'r'})
    @mock.patch('slam.cli._build')
    def test_cli_build_rebuild_deps(self, _build, _load_config):
        cli.main(['build', '--rebuild-deps'])
        _build.assert_called_once_with({'requirements': 'r'},
                                       rebuild_deps=True)
