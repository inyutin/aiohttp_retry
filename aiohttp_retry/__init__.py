import asyncio
import logging
from aiohttp import ClientSession, ClientResponse
from typing import Any, Callable, Optional, Set, Type

# Options
_RETRY_ATTEMPTS = 3
_RETRY_START_TIMEOUT = 0.1
_RETRY_MAX_TIMEOUT = 30
_RETRY_FACTOR = 2


class _RequestContext:
    def __init__(self, request: Callable[..., Any],  # Request operation, like POST or GET
                 url: str,  # Just url
                 retry_attempts: int = _RETRY_ATTEMPTS,  # How many times we should retry
                 retry_start_timeout: float = _RETRY_START_TIMEOUT,  # Base timeout time, then it exponentially grow
                 retry_max_timeout: float = _RETRY_MAX_TIMEOUT,  # Max possible timeout between tries
                 retry_factor: float = _RETRY_FACTOR,  # How much we increase timeout each time
                 retry_for_statuses: Optional[Set[int]] = None,  # On which statuses we should retry
                 retry_exceptions: Optional[Set[Type]] = None,  # On which exceptions we should retry
                 **kwargs: Any
                 ) -> None:
        self._request = request
        self._url = url

        self._retry_attempts = retry_attempts
        self._retry_start_timeout = retry_start_timeout
        self._retry_max_timeout = retry_max_timeout
        self._retry_factor = retry_factor

        if retry_for_statuses is None:
            retry_for_statuses = set()
        self._retry_for_statuses = retry_for_statuses

        if retry_exceptions is None:
            retry_exceptions = set()
        self._retry_exceptions = retry_exceptions

        self._kwargs = kwargs

        self._current_attempt = 0
        self._response: Optional[ClientResponse] = None

    def _exponential_timeout(self) -> float:
        timeout = self._retry_start_timeout * (self._retry_factor ** (self._current_attempt - 1))
        return min(timeout, self._retry_max_timeout)

    def _check_code(self, code: int) -> bool:
        return 500 <= code <= 599 or code in self._retry_for_statuses

    async def _do_request(self) -> ClientResponse:
        try:
            self._current_attempt += 1
            response: ClientResponse = await self._request(self._url, **self._kwargs)
            code = response.status
            if self._current_attempt < self._retry_attempts and self._check_code(code):
                retry_wait = self._exponential_timeout()
                await asyncio.sleep(retry_wait)
                return await self._do_request()
            self._response = response
            return response

        except Exception as e:
            retry_wait = self._exponential_timeout()
            if self._current_attempt < self._retry_attempts:
                for exc in self._retry_exceptions:
                    if isinstance(e, exc):
                        await asyncio.sleep(retry_wait)
                        return await self._do_request()

            raise e

    async def __aenter__(self) -> ClientResponse:
        return await self._do_request()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._response is not None:
            if not self._response.closed:
                self._response.close()


class RetryClient:
    def __init__(self, logger: Any = None, *args: Any, **kwargs: Any) -> None:
        self._client = ClientSession(*args, **kwargs)
        self._closed = False

        if logger is None:
            logger = logging.getLogger("aiohttp_retry")

        self._logger = logger

    def __del__(self) -> None:
        if not self._closed:
            self._logger.warning("Aiohttp retry client was not closed")

    @staticmethod
    def _request(request: Callable[..., Any], url: str, **kwargs: Any) -> _RequestContext:
        return _RequestContext(request, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.get, url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.options, url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.head, url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.post, url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.put, url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.patch, url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.delete, url, **kwargs)

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
