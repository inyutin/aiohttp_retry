import asyncio
import logging
import sys
from abc import abstractmethod

from aiohttp import ClientSession, ClientResponse
from typing import Any, Callable, Generator, Optional, Set, Type

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol


class _Logger(Protocol):
    """
    _Logger defines which methods logger object should have
    """

    @abstractmethod
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: pass

    @abstractmethod
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: pass


class RetryOptions:
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: Optional[Set[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Set[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        self.attempts: int = attempts
        self.start_timeout: float = start_timeout
        self.max_timeout: float = max_timeout
        self.factor: float = factor

        if statuses is None:
            statuses = set()
        self.statuses: Set[int] = statuses

        if exceptions is None:
            exceptions = set()
        self.exceptions: Set[Type[Exception]] = exceptions


class _RequestContext:
    def __init__(
        self,
        request: Callable[..., Any],  # Request operation, like POST or GET
        url: str,  # Just url
        logger: _Logger,
        retry_options: RetryOptions,
        **kwargs: Any
    ) -> None:
        self._request = request
        self._url = url
        self._logger = logger
        self._retry_options = retry_options
        self._kwargs = kwargs

        self._current_attempt = 0
        self._response: Optional[ClientResponse] = None

    def _exponential_timeout(self) -> float:
        timeout = self._retry_options.start_timeout * (self._retry_options.factor ** (self._current_attempt - 1))
        return min(timeout, self._retry_options.max_timeout)

    def _check_code(self, code: int) -> bool:
        return 500 <= code <= 599 or code in self._retry_options.statuses

    async def _do_request(self) -> ClientResponse:
        try:
            self._current_attempt += 1
            self._logger.debug("Attempt {} out of {}".format(self._current_attempt, self._retry_options.attempts))
            response: ClientResponse = await self._request(self._url, **self._kwargs)
            code = response.status
            if self._current_attempt < self._retry_options.attempts and self._check_code(code):
                retry_wait = self._exponential_timeout()
                await asyncio.sleep(retry_wait)
                return await self._do_request()
            self._response = response
            return response

        except Exception as e:
            retry_wait = self._exponential_timeout()
            if self._current_attempt < self._retry_options.attempts:
                for exc in self._retry_options.exceptions:
                    if isinstance(e, exc):
                        await asyncio.sleep(retry_wait)
                        return await self._do_request()

            raise e

    def __await__(self) -> Generator[Any, None, ClientResponse]:
        return self.__aenter__().__await__()

    async def __aenter__(self) -> ClientResponse:
        return await self._do_request()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._response is not None:
            if not self._response.closed:
                self._response.close()


class RetryClient:
    def __init__(
        self,
        logger: Optional[_Logger] = None,
        retry_options: RetryOptions = RetryOptions(),
        *args: Any, **kwargs: Any
    ) -> None:
        self._client = ClientSession(*args, **kwargs)
        self._closed = False

        if logger is None:
            logger = logging.getLogger("aiohttp_retry")

        self._logger: _Logger = logger
        self._retry_options: RetryOptions = retry_options

    def __del__(self) -> None:
        if not self._closed:
            self._logger.warning("Aiohttp retry client was not closed")

    def _request(
        self,
        request: Callable[..., Any],
        url: str,
        logger: _Logger,
        retry_options: Optional[RetryOptions] = None,
        **kwargs: Any
    ) -> _RequestContext:
        if retry_options is None:
            retry_options = self._retry_options
        return _RequestContext(request, url, logger, retry_options, **kwargs)

    def get(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.get, url, self._logger, retry_options, **kwargs)

    def options(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.options, url, self._logger, retry_options, **kwargs)

    def head(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.head, url, self._logger, retry_options, **kwargs)

    def post(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.post, url, self._logger, retry_options, **kwargs)

    def put(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.put, url, self._logger, retry_options, **kwargs)

    def patch(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.patch, url, self._logger, retry_options, **kwargs)

    def delete(self, url: str, retry_options: Optional[RetryOptions] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.delete, url, self._logger, retry_options, **kwargs)

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
