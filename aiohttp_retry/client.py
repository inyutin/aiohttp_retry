import asyncio
import logging
import sys
from abc import abstractmethod
from typing import Any, Callable, Generator, List, Optional, Tuple, Union

from aiohttp import ClientResponse, ClientSession, hdrs
from aiohttp.typedefs import StrOrURL
from yarl import URL as YARL_URL

from .retry_options import ExponentialRetry, RetryOptionsBase

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


# url itself or list of urls for changing between retries
_RAW_URL_TYPE = Union[StrOrURL, YARL_URL]
_URL_TYPE = Union[_RAW_URL_TYPE, List[_RAW_URL_TYPE], Tuple[_RAW_URL_TYPE, ...]]


class _RequestContext:
    def __init__(
        self,
        request: Callable[..., Any],  # Request operation, like POST or GET
        method: str,
        urls: Tuple[StrOrURL, ...],
        logger: _Logger,
        retry_options: RetryOptionsBase,
        raise_for_status: bool = False,
        **kwargs: Any
    ) -> None:
        self._request = request
        self._method = method
        self._urls = urls
        self._logger = logger
        self._retry_options = retry_options
        self._kwargs = kwargs
        self._trace_request_ctx = kwargs.pop('trace_request_ctx', {})
        self._raise_for_status = raise_for_status

        self._response: Optional[ClientResponse] = None

    def _is_status_code_ok(self, code: int) -> bool:
        return code not in self._retry_options.statuses and code < 500

    async def _do_request(self) -> ClientResponse:
        current_attempt = 0
        while True:
            self._logger.debug("Attempt {} out of {}".format(current_attempt, self._retry_options.attempts))
            if current_attempt > 0:
                retry_wait = self._retry_options.get_timeout(current_attempt)
                await asyncio.sleep(retry_wait)

            current_attempt += 1
            try:
                response: ClientResponse = await self._request(
                    self._method,
                    self._urls[current_attempt - 1],
                    **self._kwargs,
                    trace_request_ctx={
                        'current_attempt': current_attempt,
                        **self._trace_request_ctx,
                    },
                )
            except Exception as e:
                if current_attempt < self._retry_options.attempts:
                    is_exc_valid = any([isinstance(e, exc) for exc in self._retry_options.exceptions])
                    if is_exc_valid:
                        continue

                raise e

            if self._is_status_code_ok(response.status) or current_attempt == self._retry_options.attempts:
                if self._raise_for_status:
                    response.raise_for_status()
                self._response = response
                return response

    def __await__(self) -> Generator[Any, None, ClientResponse]:
        return self.__aenter__().__await__()

    async def __aenter__(self) -> ClientResponse:
        return await self._do_request()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._response is not None:
            if not self._response.closed:
                self._response.close()


def _url_to_urls(url: _URL_TYPE, attempts: int) -> Tuple[StrOrURL, ...]:
    if isinstance(url, str) or isinstance(url, YARL_URL):
        return (url,) * attempts

    if isinstance(url, list):
        urls = tuple(url)
    elif isinstance(url, tuple):
        urls = url
    else:
        raise ValueError("you can pass url only by str or list/tuple")

    if len(urls) == 0:
        raise ValueError("you can pass url by str or list/tuple with attempts count size")

    if len(urls) < attempts:
        return urls + (urls[-1],) * (attempts - len(url))

    return urls


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
        method: str,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        if retry_options is None:
            retry_options = self._retry_options
        if raise_for_status is None:
            raise_for_status = self._raise_for_status
        return _RequestContext(
            request=self._client.request,
            method=method,
            urls=_url_to_urls(url, retry_options.attempts),
            logger=self._logger,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def request(
        self,
        method: str,
        url: StrOrURL,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=method,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def get(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_GET,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def options(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_OPTIONS,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def head(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None, **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_HEAD,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def post(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_POST,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def put(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_PUT,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def patch(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_PATCH,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    def delete(
        self,
        url: _URL_TYPE,
        retry_options: Optional[RetryOptionsBase] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any
    ) -> _RequestContext:
        return self._request(
            method=hdrs.METH_DELETE,
            url=url,
            retry_options=retry_options,
            raise_for_status=raise_for_status,
            **kwargs
        )

    async def close(self) -> None:
        await self._client.close()
        self._closed = True

    async def __aenter__(self) -> 'RetryClient':
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
