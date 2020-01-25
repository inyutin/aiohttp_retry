from aiohttp_retry import RetryClient
from tests.app import TestApp


async def test_hello(aiohttp_client, loop):
    test_app = TestApp()
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


async def test_internal_error(aiohttp_client, loop):
    test_app = TestApp()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    async with retry_client.get('/internal_error', retry_attempts=5) as response:
        assert response.status == 500
        assert test_app.counter == 5

    await retry_client.close()
    await client.close()


async def test_not_found_error(aiohttp_client, loop):
    test_app = TestApp()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    async with retry_client.get('/not_found_error', retry_attempts=5, retry_for_statuses={404}) as response:
        assert response.status == 404
        assert test_app.counter == 5

    await retry_client.close()
    await client.close()


async def test_sometimes_error(aiohttp_client, loop):
    test_app = TestApp()
    app = test_app.get_app()

    client = await aiohttp_client(app)
    retry_client = RetryClient()
    retry_client._client = client

    async with retry_client.get('/sometimes_error', retry_attempts=5) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()
    await client.close()
