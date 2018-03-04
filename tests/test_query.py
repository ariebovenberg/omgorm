import inspect
import sys

import pytest
from gentools import py2_compatible, return_

import snug

try:
    import urllib.request as urllib
    from unittest import mock
except ImportError:
    import urllib2 as urllib
    import mock


live = pytest.mark.skipif(not pytest.config.getoption('--live'),
                          reason='skip live data test')
py3 = pytest.mark.skipif(sys.version_info < (3, ), reason='python 3+ only')


class MockClient(object):
    def __init__(self, response):
        self.response = response

    def send(self, req):
        self.request = req
        return self.response


snug.send.register(MockClient, MockClient.send)


def test__execute__():

    class StringClient:
        def __init__(self, mappings):
            self.mappings = mappings

        def send(self, req):
            return self.mappings[req]

    snug.send.register(StringClient, StringClient.send)

    client = StringClient({
        'foo/posts/latest': 'redirect:/posts/latest/',
        'foo/posts/latest/': 'redirect:/posts/december/',
        'foo/posts/december/': b'hello world'
    })

    class MyQuery(object):
        @py2_compatible
        def __iter__(self):
            redirect = yield '/posts/latest'
            redirect = yield redirect.split(':')[1]
            response = yield redirect.split(':')[1]
            return_(response.decode('ascii'))

    assert snug.query._default_execute_method(
        MyQuery(),
        client=client,
        authenticate=lambda s: 'foo' + s) == 'hello world'


@py2_compatible
def myquery():
    return_((yield snug.GET('my/url')))


class TestExecute:

    @mock.patch('snug.query.send', autospec=True)
    def test_defaults(self, send):

        assert snug.execute(myquery()) == send.return_value
        client, req = send.call_args[0]
        assert isinstance(client, urllib.OpenerDirector)
        assert req == snug.GET('my/url')

    def test_custom_client(self):
        client = MockClient(snug.Response(204))

        result = snug.execute(myquery(), client=client)
        assert result == snug.Response(204)
        assert client.request == snug.GET('my/url')

    def test_custom_execute(self):
        client = MockClient(snug.Response(204))

        class MyQuery(object):
            def __execute__(self, client, authenticate):
                return client.send(snug.GET('my/url'))

        result = snug.execute(MyQuery(), client=client)
        assert result == snug.Response(204)
        assert client.request == snug.GET('my/url')

    def test_auth(self):
        client = MockClient(snug.Response(204))

        result = snug.execute(myquery(),
                              auth=('user', 'pw'),
                              client=client)
        assert result == snug.Response(204)
        assert client.request == snug.GET(
            'my/url', headers={'Authorization': 'Basic dXNlcjpwdw=='})

    def test_auth_method(self):

        def token_auth(token, request):
            return request.with_headers({
                'Authorization': 'Bearer {}'.format(token)
            })

        client = MockClient(snug.Response(204))
        result = snug.execute(myquery(), auth='foo', client=client,
                              auth_method=token_auth)

        assert result == snug.Response(204)
        assert client.request == snug.GET(
            'my/url', headers={'Authorization': 'Bearer foo'})


def test_executor():
    executor = snug.executor(client='foo')
    assert executor.keywords == {'client': 'foo'}


def test_async_executor():
    executor = snug.async_executor(client='foo')
    assert executor.keywords == {'client': 'foo'}


def test_relation():

    class Foo:

        @snug.related
        class Bar(snug.Query):
            def __iter__(self): pass

            def __init__(self, a, b):
                self.a, self.b = a, b

        class Qux(snug.Query):
            def __iter__(self): pass

            def __init__(self, a, b):
                self.a, self.b = a, b

    f = Foo()
    bar = f.Bar(b=4)
    assert isinstance(bar, Foo.Bar)
    assert bar.a is f
    bar2 = Foo.Bar(f, 4)
    assert isinstance(bar2, Foo.Bar)
    assert bar.a is f

    # staticmethod opts out
    qux = f.Qux(1, 2)
    assert isinstance(qux, f.Qux)
    qux2 = Foo.Qux(1, 2)
    assert isinstance(qux2, Foo.Qux)


def test_identity():
    obj = object()
    assert snug.query._identity(obj) is obj


@py3
def test__execute_async__(loop):
    from .py3_only import awaitable

    class StringClient:
        def __init__(self, mappings):
            self.mappings = mappings

        def send(self, req):
            return self.mappings[req]

    snug.send_async.register(StringClient, StringClient.send)

    client = StringClient({
        'foo/posts/latest': awaitable('redirect:/posts/latest/'),
        'foo/posts/latest/': awaitable('redirect:/posts/december/'),
        'foo/posts/december/': awaitable(b'hello world'),
    })

    class MyQuery:

        @py2_compatible
        def __iter__(self):
            redirect = yield '/posts/latest'
            redirect = yield redirect.split(':')[1]
            response = yield redirect.split(':')[1]
            return_(response.decode('ascii'))

    future = snug.Query.__execute_async__(
        MyQuery(),
        client=client,
        authenticate=lambda s: 'foo' + s)

    if sys.version_info > (3, 5):
        assert inspect.isawaitable(future)

    result = loop.run_until_complete(future)
    assert result == 'hello world'


@py3
class TestExecuteAsync:

    def test_defaults(self, loop):
        import asyncio
        from .py3_only import awaitable

        with mock.patch('snug._async.send_async',
                        return_value=awaitable(snug.Response(204))) as send:

            future = snug.execute_async(myquery())
            result = loop.run_until_complete(future)
            assert result == snug.Response(204)
            client, req = send.call_args[0]
            assert isinstance(client, asyncio.AbstractEventLoop)
            assert req == snug.GET('my/url')

    def test_custom_client(self, loop):
        from .py3_only import MockAsyncClient
        client = MockAsyncClient(snug.Response(204))

        future = snug.execute_async(myquery(), client=client)
        result = loop.run_until_complete(future)
        assert result == snug.Response(204)
        assert client.request == snug.GET('my/url')

    def test_custom_execute(self, loop):
        from .py3_only import MockAsyncClient
        client = MockAsyncClient(snug.Response(204))

        class MyQuery:
            def __execute_async__(self, client, authenticate):
                return client.send(snug.GET('my/url'))

        future = snug.execute_async(MyQuery(), client=client)
        result = loop.run_until_complete(future)
        assert result == snug.Response(204)
        assert client.request == snug.GET('my/url')

    def test_auth(self, loop):
        from .py3_only import MockAsyncClient
        client = MockAsyncClient(snug.Response(204))

        future = snug.execute_async(myquery(),
                                    auth=('user', 'pw'),
                                    client=client)
        result = loop.run_until_complete(future)
        assert result == snug.Response(204)
        assert client.request == snug.GET(
            'my/url', headers={'Authorization': 'Basic dXNlcjpwdw=='})

    def test_auth_method(self, loop):
        from .py3_only import MockAsyncClient

        def token_auth(token, request):
            return request.with_headers({
                'Authorization': 'Bearer {}'.format(token)
            })

        client = MockAsyncClient(snug.Response(204))
        future = snug.execute_async(myquery(), auth='foo', client=client,
                                    auth_method=token_auth)
        result = loop.run_until_complete(future)

        assert result == snug.Response(204)
        assert client.request == snug.GET(
            'my/url', headers={'Authorization': 'Bearer foo'})
