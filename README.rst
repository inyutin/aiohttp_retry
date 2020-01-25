Simple aiohttp retry client
===========================

| This package is similar to `Tornado-retry-client <https://github.com/wpjunior/tornado-retry-client>`__.
| Python 3.5+.

| **Install**: ``pip install aiohttp-retry``.

**Github**: https://github.com/inyutin/aiohttp_retry

Examples of usage:
~~~~~~~~~~~~~~~~~~

.. code:: python

    from aiohttp_retry import RetryClient

    async def main():
        retry_client = RetryClient(raise_for_status=False)
        async with retry_client.get('https://ya.ru', retry_attempts=1) as response:
            print(response.status)

        await retry_client.close()

.. code:: python

    from aiohttp_retry import RetryClient

    async def main():
        async with RetryClient() as client:
            async with client.get('https://ya.ru') as response:
                print(response.status)

| Be aware: last request returns as it is.

Documentation
~~~~~~~~~~~~~

| ``RetryClient`` takes the same arguments as ClientSession[`docs <https://docs.aiohttp.org/en/stable/client_reference.html>`__\ ]
| ``RetryClient`` has methods:
| - get
| - options
| - head
| - post
| - put
| - patch
| - put
| - delete



They are same as for ``ClientSession``, but take additional arguments:

.. code:: python

    from typing import Optional, Set, Type

    retry_attempts: int = 3,  # How many times we should retry
    retry_start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
    retry_max_timeout: float = 30,  # Max possible timeout between tries
    retry_factor: float = 2,  # How much we increase timeout each time
    retry_for_statuses: Optional[Set[int]] = None,  # On which statuses we should retry
    retry_exceptions: Optional[Set[Type]] = None,  # On which exceptions we should retry


