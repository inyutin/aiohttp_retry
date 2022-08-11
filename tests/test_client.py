from types import SimpleNamespace
from typing import Optional, Tuple

import pytest
from aiohttp import (
    BasicAuth,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    TraceConfig,
    TraceRequestStartParams,
    hdrs,
)
from yarl import URL

from aiohttp_retry import ExponentialRetry, ListRetry, RetryClient
from aiohttp_retry.client import RequestParams
from aiohttp_retry.retry_options import RetryOptionsBase
from tests.app import App


async def get_retry_client_and_test_app_for_test(
    aiohttp_client,
    raise_for_status: bool = False,
    retry_options: Optional[RetryOptionsBase] = None,
) -> Tuple[RetryClient, App]:
    test_app = App()
    app = test_app.web_app()
    client = await aiohttp_client(app, raise_for_status=raise_for_status)

    retry_client = RetryClient(client_session=client, retry_options=retry_options)
    return retry_client, test_app


async def test_hello(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.get('/ping') as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()


async def test_hello_by_request(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.request(method=hdrs.METH_GET, url='/ping') as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()


async def test_hello_with_context(aiohttp_client):
    test_app = App()
    app = test_app.web_app()
    client = await aiohttp_client(app)
    async with RetryClient() as retry_client:
        retry_client._client = client
        async with retry_client.get('/ping') as response:
            text = await response.text()
            assert response.status == 200
            assert text == 'Ok!'

            assert test_app.counter == 1


async def test_internal_error(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    retry_options = ExponentialRetry(attempts=5)
    async with retry_client.get('/internal_error', retry_options) as response:
        assert response.status == 500
        assert test_app.counter == 5

    await retry_client.close()


async def test_not_found_error(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    retry_options = ExponentialRetry(attempts=5, statuses={404})
    async with retry_client.get('/not_found_error', retry_options) as response:
        assert response.status == 404
        assert test_app.counter == 5

    await retry_client.close()


async def test_sometimes_error(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    retry_options = ExponentialRetry(attempts=5)
    async with retry_client.get('/sometimes_error', retry_options) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()


async def test_sometimes_error_with_raise_for_status(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client, raise_for_status=True)
    retry_options = ExponentialRetry(attempts=5, exceptions={ClientResponseError})
    async with retry_client.get('/sometimes_error', retry_options) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()


async def test_override_options(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(
        aiohttp_client,
        retry_options=ExponentialRetry(attempts=1)
    )
    retry_options = ExponentialRetry(attempts=5)
    async with retry_client.get('/sometimes_error', retry_options) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    await retry_client.close()


async def test_hello_awaitable(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    response = await retry_client.get('/ping')
    text = await response.text()
    assert response.status == 200
    assert text == 'Ok!'

    assert test_app.counter == 1

    await retry_client.close()


async def test_add_trace_request_ctx(aiohttp_client):
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
        test_app.web_app(),
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


@pytest.mark.parametrize("attempts", [2, 3])
async def test_change_urls_in_request(aiohttp_client, attempts):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(
        aiohttp_client,
        retry_options=ExponentialRetry(attempts=attempts)
    )
    async with retry_client.get(url=['/internal_error', '/ping']) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 2

    await retry_client.close()


@pytest.mark.parametrize("attempts", [2, 3])
async def test_change_urls_as_tuple_in_request(aiohttp_client, attempts):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(
        aiohttp_client,
        retry_options=ExponentialRetry(attempts=attempts)
    )
    async with retry_client.get(url=('/internal_error', '/ping')) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 2

    await retry_client.close()


@pytest.mark.parametrize("url", [{"/ping", "/internal_error"}, []])
async def test_pass_bad_urls(aiohttp_client, url):
    retry_client, _ = await get_retry_client_and_test_app_for_test(aiohttp_client)
    with pytest.raises(ValueError):
        async with retry_client.get(url=url):
            pass

    await retry_client.close()


@pytest.mark.parametrize("url, method", [
    ("/options_handler", 'options'),
    ("/head_handler", 'head'),
    ("/post_handler", 'post'),
    ("/put_handler", 'put'),
    ("/patch_handler", 'patch'),
    ("/delete_handler", 'delete'),
])
async def test_methods(aiohttp_client, url, method):
    retry_client, _ = await get_retry_client_and_test_app_for_test(aiohttp_client)
    method_func = getattr(retry_client, method)
    async with method_func(url) as response:
        assert response.method.lower() == method

    await retry_client.close()


async def test_not_found_error_with_retry_client_raise_for_status(aiohttp_client):
    test_app = App()
    app = test_app.web_app

    client = await aiohttp_client(app)
    retry_client = RetryClient(raise_for_status=True)
    retry_client._client = client

    retry_options = ExponentialRetry(attempts=5, statuses={404})
    override_response = retry_client.get('/not_found_error', retry_options, raise_for_status=False)
    assert not override_response._raise_for_status
    response = retry_client.get('/not_found_error', retry_options)
    assert response._raise_for_status

    try:
        async with response:
            pass
    except ClientResponseError as exc:
        assert exc.status == 404
        assert test_app.counter == 5
    else:
        raise AssertionError('Expected ClientResponseError not raised')

    await retry_client.close()
    await client.close()


async def test_request(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.request(hdrs.METH_GET, '/ping') as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()


async def test_url_as_yarl(aiohttp_client):
    """https://github.com/inyutin/aiohttp_retry/issues/41"""
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.get(URL('/ping')) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()


async def test_change_client_retry_options(aiohttp_client):
    retry_options = ExponentialRetry(attempts=5)
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client, retry_options=retry_options)

    # first time with 5 attempts is okay
    async with retry_client.get('/sometimes_error') as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 3

    test_app.counter = 0
    retry_client.retry_options.attempts = 2

    # second time with 5 attempts is error
    async with retry_client.get('/sometimes_error') as response:
        text = await response.text()
        assert response.status == 500
        assert test_app.counter == 2

    await retry_client.close()


async def test_not_retry_server_errors(aiohttp_client):
    retry_options = ExponentialRetry(retry_all_server_errors=False)
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.get('/internal_error', retry_options) as response:
        assert response.status == 500
        assert test_app.counter == 1

    await retry_client.close()


async def test_list_retry_works_for_multiple_attempts(aiohttp_client):
    retry_options = ListRetry(timeouts=[0]*3)
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)

    async with retry_client.get('/internal_error', retry_options) as response:
        assert response.status == 500
        assert test_app.counter == 3

    await retry_client.close()


async def test_implicit_client(aiohttp_client):
    # check that if client not passed that it created implicitly
    test_app = App()

    retry_client = RetryClient()
    assert retry_client._client is not None

    retry_client._client = await aiohttp_client(test_app.web_app())
    async with retry_client.get('/ping') as response:
        assert response.status == 200

    await retry_client.close()


async def test_evaluate_response_callback(aiohttp_client):
    async def evaluate_response(response: ClientResponse) -> bool:
        try:
            await response.json()
        except:
            return False
        return True

    retry_options = ExponentialRetry(attempts=5, evaluate_response_callback=evaluate_response)
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client, retry_options=retry_options)

    async with retry_client.get('/sometimes_json') as response:
        body = await response.json()
        assert response.status == 200
        assert body == {'status': 'Ok!'}

        assert test_app.counter == 3


async def test_multiply_urls_by_requests(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.requests(
        params_list=[
            RequestParams(
                method='GET',
                url='/internal_error',
            ),
            RequestParams(
                method='GET',
                url='/ping',
            ),
        ]
    ) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 2

    await retry_client.close()


async def test_multiply_methods_by_requests(aiohttp_client):
    retry_options = ExponentialRetry(statuses={405})  # method not allowed
    retry_client, _ = await get_retry_client_and_test_app_for_test(aiohttp_client, retry_options=retry_options)
    async with retry_client.requests(
        params_list=[
            RequestParams(
                method='POST',
                url='/ping',
            ),
            RequestParams(
                method='GET',
                url='/ping',
            ),
        ]
    ) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

    await retry_client.close()


async def test_change_headers(aiohttp_client):
    retry_options = ExponentialRetry(statuses={406})
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client, retry_options=retry_options)
    async with retry_client.requests(
        params_list=[
            RequestParams(
                method='GET',
                url='/check_headers',
            ),
            RequestParams(
                method='GET',
                url='/check_headers',
                headers={'correct_headers': 'True'},
            ),
        ]
    ) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 2

    await retry_client.close()


async def test_additional_params(aiohttp_client):
    # https://github.com/inyutin/aiohttp_retry/issues/79
    auth = BasicAuth("username", "password")
    retry_client, _ = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.request(hdrs.METH_GET, '/with_auth', auth=auth) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

    await retry_client.close()


async def test_request_headers(aiohttp_client):
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)
    async with retry_client.get(url='/check_headers', headers={'correct_headers': 'True'}) as response:
        text = await response.text()
        assert response.status == 200
        assert text == 'Ok!'

        assert test_app.counter == 1

    await retry_client.close()


async def test_list_retry_all_failed(aiohttp_client):
    # there was a specific bug
    async def evaluate_response(response: ClientResponse) -> bool:
        return False

    retry_options = ListRetry(timeouts=[1]*3, statuses={403}, evaluate_response_callback=evaluate_response)
    retry_client, test_app = await get_retry_client_and_test_app_for_test(aiohttp_client)

    async with retry_client.get('/with_auth', retry_options=retry_options) as response:
        assert response.status == 403
        assert test_app.counter == 3

    await retry_client.close()
