import asyncio
import aiohttp

async def main():
    async with aiohttp.ClientSession() as s:
        url = "https://didasko.cz/?dgwt_wcas=1&s=9788090024069" # Ajax search standard param
        async with s.get(url, headers={"X-Requested-With": "XMLHttpRequest"}) as r:
            print("Status:", r.status)
            print(await r.text())

asyncio.run(main())
