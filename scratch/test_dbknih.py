import asyncio
import aiohttp
import re
import sys
import urllib.parse

async def fetch_databazeknih_cz(session, query: str) -> dict | None:
    encoded_query = urllib.parse.quote(query).replace("%20", "+")
    url = f"https://www.databazeknih.cz/search?q={encoded_query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with session.get(url, headers=headers, allow_redirects=True) as resp:
        print(f"DEBUG: Databáze knih status: {resp.status}, Final URL: {resp.url}")
        if resp.status != 200: return None
        text = await resp.text()
        final_url = str(resp.url)
        
    if "/knihy/" not in final_url and "/prehled-knihy/" not in final_url:
        match = re.search(r'href=["\'](?:https://www.databazeknih.cz)?/((?:prehled-knihy|knihy)/[^"\']+)["\']', text)
        if not match: 
            print("DEBUG: Databáze knih nenalezla odkaz v výsledcích")
            return None
        url = "https://www.databazeknih.cz/" + match.group(1)
        print(f"DEBUG: Databáze knih nalezen odkaz: {url}")
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
    else:
        url = final_url

    title_match = re.search(r'<h1[^>]* itemprop="name">([^<]+)</h1>', text)
    title = title_match.group(1).strip() if title_match else "Unknown"
    print(f"DEBUG: Databáze knih nalezen titul: {title}")
    return {"title": title, "url": url}

async def main():
    async with aiohttp.ClientSession() as session:
        res = await fetch_databazeknih_cz(session, "9788088447634")
        print(f"VÝSLEDEK: {res}")

if __name__ == "__main__":
    asyncio.run(main())
