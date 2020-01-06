# Simple aiohttp retry client

This package is similar to [Tornado-retry-client](https://github.com/wpjunior/tornado-retry-client). \
Python 3.5+.

### Example of usage:
```python
async def test():
    async with ClientSession() as client:
        retry_client = RetryClient(client)
        async with retry_client.get("https://google.com") as response:
            text = await response.text()
            print(text)
        await retry_client.close()
```
Look tests for more examples. \
Be aware: last request returns as it is.

### Documentation
`RetryClient` takes a single argument: `ClientSession`. \
`RetryClient` has methods:
- get
- options
- head
- post
- put
- patch
- put
- delete

They are same as for `ClientSession`, but take additional arguments: 
```python
from typing import Optional, Set, Type

retry_attempts: int = 3,  # How many times we should retry
retry_start_timeout: float = 0.1,  # Base timeout time, then it exponentially grow
retry_max_timeout: float = 30,  # Max possible timeout between tries
retry_factor: float = 2,  # How much we increase timeout each time
retry_for_statuses: Optional[Set[int]] = None,  # On which statuses we should retry
retry_exceptions: Optional[Set[Type]] = None,  # On which exceptions we should retry
```

### Development
Before creating PR please run mypy: `mypy -m aiohttp_retry`

### ToDo:

- Add more tests
- Make pip package
