import random

from aiohttp_retry import (
    ExponentialRetry,
    FibonacciRetry,
    JitterRetry,
    ListRetry,
    RandomRetry,
)


def test_exponential_retry() -> None:
    retry = ExponentialRetry(attempts=10)
    timeouts = [retry.get_timeout(x) for x in range(10)]
    assert timeouts == [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 30.0]


def test_random_retry() -> None:
    retry = RandomRetry(attempts=10, random_func=random.Random(0).random)
    timeouts = [round(retry.get_timeout(x), 2) for x in range(10)]
    assert timeouts == [2.55, 2.3, 1.32, 0.85, 1.58, 1.27, 2.37, 0.98, 1.48, 1.79]


def test_list_retry() -> None:
    expected = [1.2, 2.1, 3.4, 4.3, 4.5, 5.4, 5.6, 6.5, 6.7, 7.6]
    retry = ListRetry(expected)
    timeouts = [retry.get_timeout(x) for x in range(10)]
    assert timeouts == expected


def test_fibonacci_retry() -> None:
    retry = FibonacciRetry(attempts=10, multiplier=2, max_timeout=60)
    timeouts = [retry.get_timeout(x) for x in range(10)]
    assert timeouts == [4.0, 6.0, 10.0, 16.0, 26.0, 42.0, 60, 60, 60, 60]


def test_jitter_retry() -> None:
    random.seed(10)
    retry = JitterRetry(attempts=10)
    timeouts = [retry.get_timeout(x) for x in range(10)]
    assert len(timeouts) == 10

    expected = [
        1.4,
        0.9,
        1.7,
        0.9,
        4.2,
        5.9,
        8.1,
        12.9,
        26.6,
        30.4,
    ]
    for idx, timeout in enumerate(timeouts):
        assert abs(timeout - expected[idx]) < 0.1


def test_start_time_passed_to_get_timeout() -> None:
    """Existing strategies ignore start_time (backward compatible)."""
    retry = ExponentialRetry(attempts=5)
    # With start_time=None (default) and start_time=some value, result is the same
    for attempt in range(5):
        assert retry.get_timeout(attempt) == retry.get_timeout(attempt, start_time=None)
        assert retry.get_timeout(attempt) == retry.get_timeout(attempt, start_time=12345.0)


def test_subclass_can_read_start_time() -> None:
    """Custom strategies can access start_time in get_timeout.

    A realistic use (cumulative scheduling as in issue #121) would also need
    time.monotonic() to compute elapsed time, which is too much to mock here.
    This test just verifies the parameter arrives.
    """

    class StartTimeAwareRetry(ExponentialRetry):
        def get_timeout(
            self,
            attempt: int,
            response=None,
            start_time: float | None = None,
        ) -> float:
            if start_time is not None:
                return start_time  # just echo it back
            return super().get_timeout(attempt)

    retry = StartTimeAwareRetry(attempts=5)

    assert retry.get_timeout(attempt=1, start_time=42.0) == 42.0
    assert retry.get_timeout(attempt=1, start_time=0.0) == 0.0
    assert retry.get_timeout(attempt=1) == retry.get_timeout(attempt=1, start_time=None)
