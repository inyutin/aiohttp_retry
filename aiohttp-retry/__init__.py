import asyncio
import aiohttp


class _RequestContext:
    def __init__(self, client: aiohttp.ClientSession, url: str, retry_attempts: int,
                 retry_start_timeout: float = 0.1, retry_max_timeout: float = 30,
                 retry_factor: float = 2, retry_for_statuses=None, retry_exceptions=None, **kwargs):
        self._client = client
        self._url = url

        self._retry_attempts = retry_attempts  # How many times we should retry
        self._retry_start_timeout = retry_start_timeout  # Base timeout time, than it exponentially grow
        self._retry_max_timeout = retry_max_timeout  # Max possible timeout between tries
        self._retry_factor = retry_factor  # How much we increase timeout each time

        self._retry_for_statuses = retry_for_statuses  # On which statuses we should retry
        self._retry_exceptions = retry_exceptions  # On which exceptions we should retry

        self._kwargs = kwargs

        self._current_attempt = 0
        self._response = None

    def _exponential_timeout(self):
        timeout = self._retry_start_timeout * (self._retry_factor ** (self._current_attempt - 1))
        return min(timeout, self._retry_max_timeout)

    def _check_code(self, code):
        return 500 <= code <= 599 or code in self._retry_for_statuses

    async def _do_request(self):
        try:
            self._current_attempt += 1
            response = await self._client.get(self._url, **self._kwargs)
            code = response.status
            if self._current_attempt < self._retry_attempts and self._check_code(code):
                retry_wait = self._exponential_timeout()
                await asyncio.sleep(retry_wait)
                await self._do_request()
            self._response = response
            return response

        except Exception as e:
            retry_wait = self._exponential_timeout()
            if isinstance(e, self._retry_exceptions) and self._current_attempt < self._retry_attempts:
                await asyncio.sleep(retry_wait)
                await self._do_request()

            raise e

    async def __aenter__(self):
        return await self._do_request()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._response is not None:
            self._response.close()


class RetryClient(object):
    def __init__(self, client: aiohttp.ClientSession = aiohttp.ClientSession()) -> None:

        self._client = client

    def get(self, request: str, retry_attempts: int = 3, retry_start_timeout: float = 0.1,
            retry_max_timeout: float = 30,  retry_factor: float = 2, retry_for_statuses: set = (),
            retry_exceptions: set = (), **kwargs) -> _RequestContext:
        return _RequestContext(self._client, request, retry_attempts, retry_start_timeout, retry_max_timeout,
                               retry_factor, retry_for_statuses, retry_exceptions, **kwargs)

    async def close(self):
        await self._client.close()
