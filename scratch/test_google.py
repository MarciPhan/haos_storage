import asyncio
import aiohttp
import json

async def test_google():
    isbn = "9788088447634"
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(test_google())
