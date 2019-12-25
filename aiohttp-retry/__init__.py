import logging
from functools import partial

import aiohttp


class RetryClient:
    def __init__(self, client=None, retry_attempts=3, retry_start_timeout=0,
                 retry_max_timeout=60, retry_factor=2, retry_for_statuses=None, retry_exceptions=None,
                 logger=None):

        if client:
            self._client = client
        else:
            self._client = aiohttp.ClientSession()

        self._retry_attempts = retry_attempts
        self._retry_max_timeout = retry_max_timeout
        self._retry_start_timeout = retry_start_timeout
        self._retry_exceptions = retry_exceptions
        self._retry_for_statuses = retry_for_statuses
        self._retry_factor = retry_factor
        self.logger = logger

    def fetch(self, request, **kwargs):
        kwargs.setdefault("retry_start_timeout", self._retry_start_timeout)
        kwargs.setdefault("attempts", self._retry_attempts)
        kwargs.setdefault("retry_exceptions", self._retry_exceptions)
        kwargs.setdefault("retry_factor", self._retry_factor)
        kwargs.setdefault("logger", self.logger)
        kwargs.setdefault("retry_for_statuses", self._retry_for_statuses)
        kwargs.setdefault("retry_max_timeout", self._retry_max_timeout)
        return http_retry(self._client, request, **kwargs)


def http_retry(client, request, raise_error=True, attempts=3, retry_start_timeout=0,
               retry_max_timeout=60, retry_factor=2, retry_for_statuses=None, retry_exceptions=None,
               logger=None, **kwargs):
    attempt = 0

    if not retry_exceptions:
        retry_exceptions = ()

    if not retry_for_statuses:
        retry_for_statuses = ()

    if not logger:
        logger = logging.getLogger("RetryClient")

    def _do_request(attempt):
        http_future = client.get(request, raise_error=False, **kwargs)
        http_future.add_done_callback(partial(handle_future, attempt))

    def handle_future(attempt, future_response):
        attempt += 1
        exception = future_response.exception()
        if exception:
            return handle_exception(attempt, exception)

        handle_response(attempt, future_response.result())

    def check_code(code):
        return code >= 500 and code <= 599 or code in retry_for_statuses

    def exponential_timeout(attempt):
        timeout = retry_start_timeout * (retry_factor ** (attempt - 1))
        return min(timeout, retry_max_timeout)

    def handle_response(attempt, result):
        if result.error and attempt < attempts and check_code(result.code):
            retry_wait = exponential_timeout(attempt)
            logger.warning(
                u"attempt: %d, %s request failed: %s, body: %s",
                attempt,
                result.effective_url,
                result.error,
                repr(result.body),
            )
            return ioloop.call_later(retry_wait, lambda: _do_request(attempt))

        if raise_error and result.error:
            return future.set_exception(result.error)

        future.set_result(result)

    def handle_exception(attempt, exception):
        retry_wait = exponential_timeout(attempt)
        logger.warning(
            u"attempt: %d, request failed with exception: %s", attempt, exception
        )
        if isinstance(exception, retry_exceptions) and attempt < attempts:
            return ioloop.call_later(retry_wait, lambda: _do_request(attempt))

        return future.set_exception(exception)

    _do_request(attempt)
    return future
