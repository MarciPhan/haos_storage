import asyncio
import aiohttp

async def main():
    record_id = "mkhavirov.31213"
    async with aiohttp.ClientSession() as session:
        urls = [
            f"https://www.knihovny.cz/Record/{record_id}/Export?style=MARCXML",
            f"https://www.knihovny.cz/Record/{record_id}/Export?style=EndNote",
        ]
        for u in urls:
            async with session.get(u, timeout=10) as resp:
                print(f"URL: {u} -> Status: {resp.status}")
                if resp.status == 200:
                    text = await resp.text()
                    print(text[:300])

asyncio.run(main())
