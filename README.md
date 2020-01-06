# Simple aiohttp retry client

This package is similar to [Tornado-retry-client](https://github.com/wpjunior/tornado-retry-client). \
Be aware: last request returns as it is. (look second example at **example.py**).


### Dependencies
- python >= 3.5


### Development
- run mypy: `mypy -m aiohttp_retry`


### Example of usage:
```.env
async def test():
    async with ClientSession() as client:
        retry_client = RetryClient(client)
        async with retry_client.get("https://google.com") as response:
            text = await response.text()
            print(text)
        await retry_client.close()
```
More examples can be found in **example.py**.

### ToDo:

- Add Tests
- Make better documentation
- Make pip package
