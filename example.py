from asyncio import get_event_loop
from aiohttp import ClientSession
from aiohttp_retry import RetryClient

url = 'https://how.rl.works/'  # Just simple site


async def first_example():
    print("First Example")
    async with ClientSession() as client:
        retry_client = RetryClient(client)
        async with retry_client.get(url) as response:
            text = await response.text()
            print(text)
        await retry_client.close()


async def second_example():
    print("\nSecond Example")
    async with ClientSession() as client:
        retry_client = RetryClient(client)
        async with retry_client.get(url, retry_for_statuses={200}) as response:
            text = await response.text()
            print(text)
        await retry_client.close()

if __name__ == '__main__':
    loop = get_event_loop()

    loop.run_until_complete(first_example())
    loop.run_until_complete(second_example())
