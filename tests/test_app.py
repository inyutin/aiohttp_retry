from aiohttp import ClientResponseError
import pytest

from aiohttp_retry import RetryClient, RetryOptions
from tests.app import App


async def test_hello(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    async with retry_client.get('/ping') as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()
    await client.close()


async def test_hello_with_context(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)

    async with RetryClient() as retry_client:
        retry_client._client = client
        async with retry_client.get('/ping') as response:
            text = await response.text()
            assert response.status == 200
            assert text == 'Ok!'

            assert test_app.counter == 1

    await client.close()


async def test_internal_error(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    retry_options = RetryOptions(attempts=5)
    async with retry_client.get('/internal_error', retry_options) as response:
        assert response.status == 500
        assert test_app.counter == 5

    await retry_client.close()
    await client.close()


async def test_not_found_error(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    retry_options = RetryOptions(attempts=5, statuses={404})
    async with retry_client.get('/not_found_error', retry_options) as response:
        assert response.status == 404
        assert test_app.counter == 5

    await retry_client.close()
    await client.close()


async def test_sometimes_error(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    retry_options = RetryOptions(attempts=5)
    async with retry_client.get('/sometimes_error', retry_options) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()
    await client.close()


async def test_sometimes_error_with_raise_for_status(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app, raise_for_status=True)
    retry_client = RetryClient()
    retry_client._client = client

    retry_options = RetryOptions(attempts=5, exceptions={ClientResponseError})
    async with retry_client.get('/sometimes_error', retry_options) \
            as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()
    await client.close()


async def test_override_options(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_options = RetryOptions(attempts=1)
    retry_client = RetryClient(retry_options=retry_options)
    retry_client._client = client

    retry_options = RetryOptions(attempts=5)
    async with retry_client.get('/sometimes_error', retry_options) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()
    await client.close()


async def test_hello_awaitable(aiohttp_client, loop):
    test_app = App()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    response = await retry_client.get('/ping')
    text = await response.text()
    assert response.status == 200
    assert text == 'Ok!'

    assert test_app.counter == 1

    await retry_client.close()
    await client.close()


async def test_filter_request_block_url():
    class FilteringClient(RetryClient):
        def filter_request(self, method, url, kwargs):
            if url.startswith('http://'):
                raise ValueError('only secure HTTP requests are allowed')
            return url

    client = FilteringClient()
    with pytest.raises(ValueError, match='only secure HTTP requests are allowed'):
        client.get('http://example.com')
    client.get('https://example.com')._url == 'https://example.com'


async def test_filter_request_default_headers():
    class FilteringClient(RetryClient):
        def filter_request(self, method, url, kwargs):
            headers = kwargs.setdefault('headers', {})
            headers['User-Agent'] = 'custom-agent'
            return url

    client = FilteringClient()
    client.get('')._kwargs == {'headers': {'User-Agent': 'custom-agent'}}
    client.get('', headers={'Accept-Encoding': 'gzip, deflate'})._kwargs == {
        'headers': {'Accept-Encoding': 'gzip, deflate', 'User-Agent': 'custom-agent'}}
    client.get('', headers={'User-Agent': 'python'})._kwargs == {'headers': {'User-Agent': 'custom-agent'}}


async def test_filter_request_method():
    filter_method: str

    class FilteringClient(RetryClient):
        def filter_request(self, method, url, kwargs):
            nonlocal filter_method
            filter_method = method

    client = FilteringClient()
    client.get('')
    assert filter_method == 'GET'
    client.post('')
    assert filter_method == 'POST'
    client.put('')
    assert filter_method == 'PUT'
    client.patch('')
    assert filter_method == 'PATCH'
    client.delete('')
    assert filter_method == 'DELETE'
    client.options('')
    assert filter_method == 'OPTIONS'