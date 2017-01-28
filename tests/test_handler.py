from collections import namedtuple
import os
import unittest

from slam.cli import _generate_lambda_handler

LambdaContext = namedtuple('LambdaContext', ['function_version',
                                             'invoked_function_arn'])


def app(environ, start_response):
    app.environ = environ
    w = start_response(app.status, app.headers)
    if app.write:
        w(app.write)
    return app.body


app.environ = None
app.status = '200 OK'
app.headers = []
app.write = None
app.body = [b'']


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = {'function': {'module': 'tests.test_handler', 'app': 'app'},
                  'devstage': 'dev', 'environment': {'FOO': 'bar'},
                  'stage_environments': {'dev': {'FOODEV': 'bardev'},
                                         'prod': {'FOOPROD': 'barprod'}},
                  'wsgi': {'deploy_api_gateway': True}}
        _generate_lambda_handler(config, 'slam/_handler.py')

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.context = LambdaContext(
            function_version='foo-version',
            invoked_function_arn='arn:aws:lambda:us-east-1:123456:function:'
                                 'foo-function:dev')

    def tearDown(self):
        for var in ['STAGE', 'FOO', 'FOODEV', 'FOOPROD']:
            if var in os.environ:
                del os.environ[var]

    def test_default_request(self):
        from slam._handler import lambda_handler
        rv = lambda_handler({}, self.context)
        self.assertEqual(app.environ['lambda.event'], {})
        self.assertEqual(app.environ['lambda.context'], self.context)
        self.assertEqual(app.environ['REQUEST_METHOD'], 'GET')
        self.assertEqual(app.environ['PATH_INFO'], '/')
        self.assertEqual(os.environ.get('STAGE'), 'dev')
        self.assertEqual(os.environ.get('FOO'), 'bar')
        self.assertEqual(os.environ.get('FOODEV'), 'bardev')
        self.assertEqual(os.environ.get('FOOPROD'), None)
        self.assertEqual(rv['statusCode'], 200)

    def test_prod_request(self):
        from slam._handler import lambda_handler
        context = LambdaContext(
            function_version='foo-version',
            invoked_function_arn='arn:aws:lambda:us-east-1:123456:function:'
                                 'foo-function:prod')
        context.invoked_function_arn.replace(':dev', ':prod')
        rv = lambda_handler({'stage': 'prod'}, context)
        self.assertEqual(app.environ['lambda.event'], {'stage': 'prod'})
        self.assertEqual(app.environ['lambda.context'], context)
        self.assertEqual(app.environ['REQUEST_METHOD'], 'GET')
        self.assertEqual(app.environ['PATH_INFO'], '/')
        self.assertEqual(os.environ.get('STAGE'), 'prod')
        self.assertEqual(os.environ.get('FOO'), 'bar')
        self.assertEqual(os.environ.get('FOODEV'), None)
        self.assertEqual(os.environ.get('FOOPROD'), 'barprod')
        self.assertEqual(rv['statusCode'], 200)

    def test_request_method(self):
        from slam._handler import lambda_handler
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD']:
            lambda_handler({'httpMethod': method}, self.context)
        self.assertEqual(app.environ['REQUEST_METHOD'], method)

    def test_path(self):
        from slam._handler import lambda_handler
        lambda_handler({'path': '/foo/bar'}, self.context)
        self.assertEqual(app.environ['PATH_INFO'], '/foo/bar')

    def test_query_string(self):
        from slam._handler import lambda_handler
        lambda_handler({'queryStringParameters': {
            'foo': 'bar', 'a?': 'b&'}}, self.context)
        self.assertTrue(app.environ['QUERY_STRING'] == 'a%3F=b%26&foo=bar' or
                        app.environ['QUERY_STRING'] == 'foo=bar&a%3F=b%26')

    def test_body(self):
        from slam._handler import lambda_handler
        app.write = b'baz'
        app.body = [b'foo', b'bar']
        rv = lambda_handler({'body': 'foo'}, self.context)
        self.assertEqual(app.environ['wsgi.input'].read(), b'foo')
        self.assertEqual(rv['body'], b'bazfoobar')

    def test_headers(self):
        from slam._handler import lambda_handler
        app.headers = [('bar', 'baz')]
        rv = lambda_handler({'headers': {'a': 'b', 'foo-bar': 'baz'}},
                            self.context)
        self.assertEqual(app.environ['HTTP_A'], 'b')
        self.assertEqual(app.environ['HTTP_FOO_BAR'], 'baz')
        self.assertEqual(rv['headers'], {'bar': 'baz'})

    def test_status_code(self):
        from slam._handler import lambda_handler
        app.status = '401 UNAUTHORIZED'
        rv = lambda_handler({}, self.context)
        self.assertEqual(rv['statusCode'], 401)

    def test_environment(self):
        from slam._handler import lambda_handler
        lambda_handler({'stageVariables': {'foo': 'bar'}}, self.context)
        self.assertEqual(os.environ['foo'], 'bar')
        self.assertEqual(os.environ['LAMBDA_VERSION'],
                         self.context.function_version)

    def test_generator(self):
        def g():
            yield b'foo'
            yield b'bar'
            yield b'baz'

        from slam._handler import lambda_handler
        app.write = None
        app.body = g()
        rv = lambda_handler({}, self.context)
        self.assertEqual(rv['body'], b'foobarbaz')
