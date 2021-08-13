import abc
import random
from typing import Any, Callable, Iterable, List, Optional, Set, Type
from warnings import warn


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
        super().__init__(len(timeouts), statuses, exceptions)
        self.timeouts = timeouts

    def get_timeout(self, attempt: int) -> float:
        """timeouts from a defined list."""
        return self.timeouts[attempt]


class FibonacciRetry(RetryOptionsBase):
    def __init__(
        self,
        attempts: int = 3,
        multiplier: float = 1.0,
        statuses: Optional[Iterable[int]] = None,
        exceptions: Optional[Iterable[Type[Exception]]] = None,
        max_timeout: float = 3.0,  # Maximum possible timeout between tries
    ):
        super().__init__(attempts, statuses, exceptions)

        self.max_timeout = max_timeout
        self.multiplier = multiplier
        self.prev_step = 1.0
        self.current_step = 1.0

    def get_timeout(self, attempt: int) -> float:
        new_current_step = self.prev_step + self.current_step
        self.prev_step = self.current_step
        self.current_step = new_current_step

        return min(self.multiplier * new_current_step, self.max_timeout)


class JitterRetry(ExponentialRetry):
    """https://github.com/inyutin/aiohttp_retry/issues/44"""
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
        max_timeout: float = 30.0,  # Max possible timeout between tries
        factor: float = 2.0,  # How much we increase timeout each time
        statuses: Optional[Set[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Set[Type[Exception]]] = None,  # On which exceptions we should retry
        random_interval_size: float = 2.0,  # size of interval for random component
    ):
        super().__init__(
            attempts=attempts,
            start_timeout=start_timeout,
            max_timeout=max_timeout,
            factor=factor,
            statuses=statuses,
            exceptions=exceptions,
        )

        self._start_timeout: float = start_timeout
        self._max_timeout: float = max_timeout
        self._factor: float = factor
        self._random_interval_size = random_interval_size

    def get_timeout(self, attempt: int) -> float:
        return super().get_timeout(attempt) + random.uniform(0, self._random_interval_size) ** self._factor
