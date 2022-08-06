# Simple aiohttp retry client

[![codecov](https://codecov.io/gh/inyutin/aiohttp_retry/branch/master/graph/badge.svg?token=ZWGAXSF1SP)](https://codecov.io/gh/inyutin/aiohttp_retry)

Python 3.7 or higher.

**Install**: `pip install aiohttp-retry`.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/inyutin)


### Breaking API changes
- Since 2.5.6 this is a new parameter in ```get_timeout``` func called "response".  
If you have defined your own ```RetryOptions```, you should add this param into it.
Issue about this: https://github.com/inyutin/aiohttp_retry/issues/59

### Examples of usage:
```python
from aiohttp_retry import RetryClient, ExponentialRetry

async def main():
    retry_options = ExponentialRetry(attempts=1)
    retry_client = RetryClient(raise_for_status=False, retry_options=retry_options)
    async with retry_client.get('https://ya.ru') as response:
        print(response.status)
        
    await retry_client.close()
```

```python
from aiohttp import ClientSession
from aiohttp_retry import RetryClient 

async def main():
    client_session = ClientSession()
    retry_client = RetryClient(client_session=client_session)
    async with retry_client.get('https://ya.ru') as response:
        print(response.status)

    await client_session.close()
```

```python
from aiohttp_retry import RetryClient, RandomRetry

async def main():
    retry_options = RandomRetry(attempts=1)
    retry_client = RetryClient(raise_for_status=False, retry_options=retry_options)

    response = await retry_client.get('/ping')
    print(response.status)
        
    await retry_client.close()
```

```python
from aiohttp_retry import RetryClient

async def main():
    async with RetryClient() as client:
        async with client.get('https://ya.ru') as response:
            print(response.status)
```

You can also add some logic, F.E. logging, on failures by using trace mechanic.
```python
import logging
import sys
from types import SimpleNamespace

from aiohttp import ClientSession, TraceConfig, TraceRequestStartParams

from aiohttp_retry import RetryClient, ExponentialRetry


handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=[handler])
logger = logging.getLogger(__name__)
retry_options = ExponentialRetry(attempts=2)


async def on_request_start(
    session: ClientSession,
    trace_config_ctx: SimpleNamespace,
    params: TraceRequestStartParams,
) -> None:
    current_attempt = trace_config_ctx.trace_request_ctx['current_attempt']
    if retry_options.attempts <= current_attempt:
        logger.warning('Wow! We are in last attempt')


async def main():
    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    retry_client = RetryClient(retry_options=retry_options, trace_configs=[trace_config])

    response = await retry_client.get('https://httpstat.us/503', ssl=False)
    print(response.status)

    await retry_client.close()
```
Look tests for more examples. \
**Be aware: last request returns as it is.**  
**If the last request ended with exception, that this exception will be raised from RetryClient request**

### Documentation
`RetryClient` takes the same arguments as ClientSession[[docs](https://docs.aiohttp.org/en/stable/client_reference.html)] \
`RetryClient` has methods:
- get
- options
- head
- post
- put
- patch
- put
- delete

They are same as for `ClientSession`, but take one possible additional argument: 
```python
class RetryOptionsBase:
    def __init__(
        self,
        attempts: int = 3,  # How many times we should retry
        statuses: Optional[Iterable[int]] = None,  # On which statuses we should retry
        exceptions: Optional[Iterable[Type[Exception]]] = None,  # On which exceptions we should retry
        retry_all_server_errors: bool = True,  # If should retry all 500 errors or not
        # a callback that will run on response to decide if retry
        evaluate_response_callback: Optional[EvaluateResponseCallbackType] = None,
    ):
        ...

    @abc.abstractmethod
    def get_timeout(self, attempt: int, response: Optional[Response] = None) -> float:
        raise NotImplementedError

```
You can specify `RetryOptions` both for `RetryClient` and it's methods. 
`RetryOptions` in methods override `RetryOptions` defined in `RetryClient` constructor.

**Important**: by default all 5xx responses are retried + statuses you specified as ```statuses``` param
If you will pass ```retry_all_server_errors=False``` than you can manually set what 5xx errors to retry.

You can define your own timeouts logic or use: 
- ```ExponentialRetry``` with exponential backoff
- ```RandomRetry``` for random backoff
- ```ListRetry``` with backoff you predefine by list
- ```FibonacciRetry``` with backoff that looks like fibonacci sequence
- ```JitterRetry``` exponential retry with a bit of randomness

**Important**: you can proceed server response as an parameter for calculating next timeout.  
However this response can be None, server didn't make a response or you have set up ```raise_for_status=True```
Look here for an example: https://github.com/inyutin/aiohttp_retry/issues/59

Additionally, you can specify ```evaluate_response_callback```. It receive a ```ClientResponse``` and decide to retry or not by returning a bool.
It can be useful, if server API sometimes response with malformed data.

#### Request Trace Context
`RetryClient` add *current attempt number* to `request_trace_ctx` (see examples, 
for more info see [aiohttp doc](https://docs.aiohttp.org/en/stable/client_advanced.html#aiohttp-client-tracing)).

### Change URL between retries
You can change URL between retries by specifying ```url``` as list of urls. Example:
```python
from aiohttp_retry import RetryClient

retry_client = RetryClient()
async with retry_client.get(url=['/internal_error', '/ping']) as response:
    text = await response.text()
    assert response.status == 200
    assert text == 'Ok!'

await retry_client.close()
```

In this example we request ```/interval_error```, fail and then successfully request ```/ping```.
If you specify less urls than ```attempts``` number in ```RetryOptions```, ```RetryClient``` will request last url at last attempts.
This means that in example above we would request ```/ping``` once again in case of failure.

### Types

`aiohttp_retry` is a typed project. It should be fully compatablie with mypy.

It also introduce one special type:
```
ClientType = Union[ClientSession, RetryClient]
```

This type can be imported by ```from aiohttp_retry.types import ClientType```
