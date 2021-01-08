import random
from types import SimpleNamespace

from aiohttp import ClientSession
from aiohttp import TraceConfig
from aiohttp import TraceRequestStartParams

from aiohttp_retry import RetryClient, ExponentialRetry, RandomRetry, ListRetry
from tests.app import App


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


async def test_add_trace_request_ctx(aiohttp_client, loop):
    actual_request_contexts = []

    async def on_request_start(
        _: ClientSession,
        trace_config_ctx: SimpleNamespace,
        __: TraceRequestStartParams,
    ) -> None:
        actual_request_contexts.append(trace_config_ctx)

    test_app = App()

    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)  # type: ignore

    retry_client = RetryClient()
    retry_client._client = await aiohttp_client(
        test_app.get_app(),
        trace_configs=[trace_config]
    )

    async with retry_client.get('/sometimes_error', trace_request_ctx={'foo': 'bar'}):
        assert test_app.counter == 3

    assert actual_request_contexts == [
        SimpleNamespace(
            trace_request_ctx={
                'foo': 'bar',
                'current_attempt': i + 1,
            },
        )
        for i in range(3)
    ]
