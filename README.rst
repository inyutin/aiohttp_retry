Simple aiohttp retry client
===========================

| This package is similar to
  `Tornado-retry-client <https://github.com/wpjunior/tornado-retry-client>`__.
| Python 3.5+.

**Install**: ``pip install aiohttp-retry``.

Warning
~~~~~~~

| This current version is 2.0. It hasn’t backward compatibility for
  previous versions.
| You still can use
  `v1.2 <https://github.com/inyutin/aiohttp_retry/tree/v1.2>`__ (pip
  install aiohttp-retry==1.2), but it is unsupported.

Examples of usage:
~~~~~~~~~~~~~~~~~~

.. code:: python

   from aiohttp_retry import RetryClient, RetryOptions

   async def main():
       retry_options = RetryOptions(attempts=1)
       retry_client = RetryClient(raise_for_status=False, retry_options=retry_options)
       async with retry_client.get('https://ya.ru') as response:
           print(response.status)
           
       await retry_client.close()

.. code:: python

   from aiohttp_retry import RetryClient

   async def main():
       async with RetryClient() as client:
           async with client.get('https://ya.ru') as response:
               print(response.status)

| Look tests for more examples.
| Be aware: last request returns as it is.

Documentation
~~~~~~~~~~~~~

| ``RetryClient`` takes the same arguments as
  ClientSession[`docs <https://docs.aiohttp.org/en/stable/client_reference.html>`__]
| ``RetryClient`` has methods: - get - options - head - post - put -
  patch - put - delete

They are same as for ``ClientSession``, but take one possible additional
argument:

.. code:: python

   from typing import Optional, Set, Type

   class RetryOptions:
       def __init__(
           self,
           attempts: int = 3,  # How many times we should retry
           start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
           max_timeout: float = 30.0,  # Max possible timeout between tries
           factor: float = 2.0,  # How much we increase timeout each time
           statuses: Optional[Set[int]] = None,  # On which statuses we should retry
           exceptions: Optional[Set[Type[Exception]]] = None,  # On which exceptions we should retry
       )
       ...

You can specify ``RetryOptions`` both for ``RetryClient`` and it’s
methods. ``RetryOptions`` in methods override ``RetryOptions`` defined
in ``RetryClient`` constructor.

Development
~~~~~~~~~~~

Before creating PR please run mypy: ``mypy -m aiohttp_retry``
