import abc
import asyncio
import logging
import random
import sys
from abc import abstractmethod
from warnings import warn

from aiohttp import ClientSession, ClientResponse
from typing import Any, Callable, Generator, Optional, Set, Type, Iterable, List, Union

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


_URL_TYPE = Union[str, List[str]]  # url itself or list of urls for changing between retries


class RetryOptionsBase:
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        self.attempts: int = attempts
        if statuses is None:
            statuses = set()
        self.statuses: Iterable[int] = statuses

        if exceptions is None:
            exceptions = set()
        self.exceptions: Iterable[Type[Exception]] = exceptions

    @abc.abstractmethod
    def get_timeout(self, attempt: int) -> float:
        raise NotImplementedError


class ExponentialRetry(RetryOptionsBase):
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: Optional[Set[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Set[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        super().__init__(attempts, statuses, exceptions)

        self._start_timeout: float = start_timeout
        self._max_timeout: float = max_timeout
        self._factor: float = factor

    def get_timeout(self, attempt: int) -> float:
        """Return timeout with exponential backoff."""
        timeout = self._start_timeout * (self._factor ** attempt)
        return min(timeout, self._max_timeout)


def RetryOptions(*args: Any, **kwargs: Any) -> ExponentialRetry:
    warn("RetryOptions is deprecated, use ExponentialRetry")
    return ExponentialRetry(*args, **kwargs)


class RandomRetry(RetryOptionsBase):
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
        min_timeout: float = 0.1,  # Minimum possible timeout
        max_timeout: float = 3.0,  # Maximum possible timeout between tries
        random_func: Callable[[], float] = random.random,  # Random number generator
    ):
        super().__init__(attempts, statuses, exceptions)
        self.attempts: int = attempts
        self.min_timeout: float = min_timeout
        self.max_timeout: float = max_timeout
        self.random = random_func

    def get_timeout(self, attempt: int) -> float:
        """Generate random timeouts."""
        return self.min_timeout + self.random() * (self.max_timeout - self.min_timeout)


class ListRetry(RetryOptionsBase):
    def __init__(
        self,
        timeouts: List[float],
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        self.timeouts = timeouts
        super().__init__(len(timeouts), statuses, exceptions)

    def get_timeout(self, attempt: int) -> float:
        """timeouts from a defined list."""
        return self.timeouts[attempt]


class _RequestContext:
    def __init__(
        self,
        request: Callable[..., Any],  # Request operation, like POST or GET
        urls: List[str],  # Just url
        logger: _Logger,
        retry_options: RetryOptionsBase,
        raise_for_status: bool = False,
        **kwargs: Any
    ) -> None:
        self._request = request
        self._urls = urls
        self._logger = logger
        self._retry_options = retry_options
        self._kwargs = kwargs
        self._trace_request_ctx = kwargs.pop('trace_request_ctx', {})
        self._raise_for_status = raise_for_status

        self._current_attempt = 0
        self._response: Optional[ClientResponse] = None

    def _check_code(self, code: int) -> bool:
        return 500 <= code <= 599 or code in self._retry_options.statuses

    async def _do_request(self) -> ClientResponse:
        try:
            self._current_attempt += 1
            self._logger.debug("Attempt {} out of {}".format(self._current_attempt, self._retry_options.attempts))

            response: ClientResponse = await self._request(
                self._urls[self._current_attempt - 1],
                **self._kwargs,
                trace_request_ctx={
                    'current_attempt': self._current_attempt,
                    **self._trace_request_ctx,
                },
            )
            code = response.status

            if self._current_attempt < self._retry_options.attempts and self._check_code(code):
                retry_wait = self._retry_options.get_timeout(self._current_attempt)
                await asyncio.sleep(retry_wait)
                return await self._do_request()
            self._response = response
            if self._raise_for_status:
                response.raise_for_status()
            return response

        except Exception as e:
            retry_wait = self._retry_options.get_timeout(self._current_attempt)
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
        retry_options: RetryOptionsBase = ExponentialRetry(),
        raise_for_status: bool = False,
        *args: Any, **kwargs: Any
    ) -> None:
        self._client = ClientSession(*args, **kwargs)
        self._closed = False

        if logger is None:
            logger = logging.getLogger("aiohttp_retry")

        self._logger: _Logger = logger
        self._retry_options: RetryOptionsBase = retry_options
        self._raise_for_status = raise_for_status

    def __del__(self) -> None:
        if not self._closed:
            self._logger.warning("Aiohttp retry client was not closed")

    def _request(
        self,
        request: Callable[..., Any],
        url: _URL_TYPE,
        logger: _Logger,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        if retry_options is None:
            retry_options = self._retry_options
        if isinstance(url, str):
            urls = [url] * retry_options.attempts
        elif not isinstance(url, list) or len(url) == 0:
            raise ValueError("you can pass url by str or list with attempts count size")
        elif len(url) < retry_options.attempts:
            urls = url.copy()
            last_request_urls = [url[-1]] * (retry_options.attempts - len(url))
            urls.extend(last_request_urls)
        else:
            urls = url

        if raise_for_status is None:
            raise_for_status = self._raise_for_status
        return _RequestContext(request, urls, logger, retry_options, raise_for_status, **kwargs)

    def get(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.get, url, self._logger, retry_options, raise_for_status, **kwargs)

    def options(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.options, url, self._logger, retry_options, raise_for_status, **kwargs)

    def head(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None, **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.head, url, self._logger, retry_options, raise_for_status, **kwargs)

    def post(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.post, url, self._logger, retry_options, raise_for_status, **kwargs)

    def put(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.put, url, self._logger, retry_options, raise_for_status, **kwargs)

    def patch(
        self, url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.patch, url, self._logger, retry_options, raise_for_status, **kwargs)

    def delete(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(self._client.delete, url, self._logger, retry_options, raise_for_status, **kwargs)

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
