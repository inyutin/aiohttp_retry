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
