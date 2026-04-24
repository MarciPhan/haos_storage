import asyncio
import aiohttp
import re

async def main():
    record_id = "mkhavirov.31213"
    async with aiohttp.ClientSession() as session:
        url = f"https://www.knihovny.cz/Record/{record_id}/Export?style=MARCXML"
        async with session.get(url) as resp:
            xml = await resp.text()
            
            # Find year: <datafield tag="260" ...> <subfield code="c">1994</subfield>
            # or 264
            year_match = re.search(r'<datafield tag="26[04]".*?>.*?<subfield code="c">.*?(\d{4}).*?</subfield>.*?</datafield>', xml, re.DOTALL)
            year = year_match.group(1) if year_match else None
            
            # Find publisher: <subfield code="b">Biblos,</subfield>
            pub_match = re.search(r'<datafield tag="26[04]".*?>.*?<subfield code="b">([^<]+)</subfield>.*?</datafield>', xml, re.DOTALL)
            publisher = pub_match.group(1).strip(" ,:;/") if pub_match else None
            
            # Find pages: <datafield tag="300" ...> <subfield code="a">613 s. ;</subfield>
            pages_match = re.search(r'<datafield tag="300".*?>.*?<subfield code="a">.*?(\d+).*?</subfield>.*?</datafield>', xml, re.DOTALL)
            pages = int(pages_match.group(1)) if pages_match else None
            
            print(f"Year: {year}, Pub: {publisher}, Pages: {pages}")

asyncio.run(main())
