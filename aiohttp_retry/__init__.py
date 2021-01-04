import asyncio
import itertools
import logging
import random
import sys
from abc import abstractmethod

from aiohttp import ClientSession, ClientResponse
from typing import Any, Awaitable, Callable, Generator, Iterable, Optional, Set, Tuple, Type

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


_TimeoutsGenerator = Generator[float, Tuple[Optional[ClientResponse], Optional[Exception]], None]


class RetryOptionsBase:
    def __init__(
        self,
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        self.statuses = set() if statuses is None else set(statuses)
        self.exceptions = set() if exceptions is None else set(exceptions)

    def timeouts(self) -> _TimeoutsGenerator:
        raise NotImplementedError


class RetryOptions(RetryOptionsBase):
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: Optional[Set[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Set[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        super().__init__(statuses, exceptions)
        self.attempts: int = attempts
        self.start_timeout: float = start_timeout
        self.max_timeout: float = max_timeout
        self.factor: float = factor

    def timeouts(self) -> _TimeoutsGenerator:
        """Return timeout with exponential backoff."""
        yield self.attempts
        for attempt in range(self.attempts):
            yield self.start_timeout * (self.factor ** attempt)


ExponentialRetry = RetryOptions


class RandomRetry(RetryOptionsBase):
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        min_timeout: float = 0.1,  # Minimum possible timeout
        max_timeout: float = 3.0,  # Maximum possible timeout between tries
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
        random: Callable[[], float] = random.random,  # Random number generator
    ):
        super().__init__(statuses, exceptions)
        self.attempts: int = attempts
        self.min_timeout: float = min_timeout
        self.max_timeout: float = max_timeout
        self.random = random

    def timeouts(self) -> _TimeoutsGenerator:
        """Generate random timeouts."""
        yield self.attempts
        for _ in range(self.attempts):
            yield self.min_timeout + self.random() * (self.max_timeout - self.min_timeout)


class ListRetry(RetryOptionsBase):
    def __init__(
        self,
        timeouts: Iterable[float],
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
    ):
        self.timeout_list = list(timeouts)
        super().__init__(statuses, exceptions)

    def timeouts(self) -> _TimeoutsGenerator:
        """Yield timeouts from a list."""
        yield len(self.timeout_list)
        yield from self.timeout_list


class _RequestContext:
    def __init__(
        self,
        request: Callable[..., Awaitable[ClientResponse]],  # Request operation, like POST or GET
        url: str,  # Just url
        logger: _Logger,
        retry_options: RetryOptionsBase,
        **kwargs: Any
    ) -> None:
        self._request = request
        self._url = url
        self._logger = logger
        self._retry_options = retry_options
        self._kwargs = kwargs
        self._trace_request_ctx = kwargs.pop('trace_request_ctx', {})

        self._response: Optional[ClientResponse] = None

    def _check_exception(self, exc: Exception) -> bool:
        return any(isinstance(exc, cls) for cls in self._retry_options.exceptions)

    def _check_code(self, code: int) -> bool:
        return 500 <= code <= 599 or code in self._retry_options.statuses

    async def _do_request(self) -> ClientResponse:
        response: Optional[ClientResponse] = None
        error: Optional[Exception] = None
        timeouts = self._retry_options.timeouts()
        attempts = next(timeouts)
        for attempt in itertools.count(1):
            self._logger.debug("Attempt {} out of {}".format(attempt, attempts))
            if response is not None:
                response.close()
                response = None
            try:
                response = await self._request(
                    self._url,
                    **self._kwargs,
                    trace_request_ctx={
                        'current_attempt': self._current_attempt,
                        **self._trace_request_ctx,
                    },
                )
            except Exception as exc:
                if not self._check_exception(exc):
                    raise
                error = exc
            else:
                if not self._check_code(response.status):
                    return response
            try:
                retry_wait = timeouts.send((response, error))
            except StopIteration:
                break
            await asyncio.sleep(retry_wait)
        if response is not None:
            self._response = response
            return response
        assert error is not None
        raise error

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
        retry_options: Optional[RetryOptionsBase] = None,
        *args: Any, **kwargs: Any
    ) -> None:
        self._client = ClientSession(*args, **kwargs)
        self._closed = False

        if logger is None:
            logger = logging.getLogger("aiohttp_retry")
        if retry_options is None:
            retry_options = RetryOptions()

        self._logger: _Logger = logger
        self._retry_options: RetryOptionsBase = retry_options

    def __del__(self) -> None:
        if not self._closed:
            self._logger.warning("Aiohttp retry client was not closed")

    def _request(
        self,
        request: Callable[..., Awaitable[ClientResponse]],
        url: str,
        logger: _Logger,
        retry_options: Optional[RetryOptionsBase] = None,
        **kwargs: Any
    ) -> _RequestContext:
        if retry_options is None:
            retry_options = self._retry_options
        return _RequestContext(request, url, logger, retry_options, **kwargs)

    def get(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.get, url, self._logger, retry_options, **kwargs)

    def options(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.options, url, self._logger, retry_options, **kwargs)

    def head(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.head, url, self._logger, retry_options, **kwargs)

    def post(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.post, url, self._logger, retry_options, **kwargs)

    def put(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.put, url, self._logger, retry_options, **kwargs)

    def patch(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.patch, url, self._logger, retry_options, **kwargs)

    def delete(self, url: str, retry_options: Optional[RetryOptionsBase] = None, **kwargs: Any) -> _RequestContext:
        return self._request(self._client.delete, url, self._logger, retry_options, **kwargs)

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
