import asyncio
import aiohttp
import re
import sys

async def fetch_didasko_cz(session, isbn: str) -> dict | None:
    queries = [isbn]
    if len(isbn) == 13:
        # Correct Czech pattern: 978-80-XXXXX-X-X
        queries.append(f"{isbn[:3]}-{isbn[3:5]}-{isbn[5:10]}-{isbn[10:12]}-{isbn[12:]}")
        # Another common pattern
        queries.append(f"{isbn[:3]}-{isbn[3:5]}-{isbn[5:9]}-{isbn[9:12]}-{isbn[12:]}")
        # One more
        queries.append(f"{isbn[:3]}-{isbn[3:4]}-{isbn[4:9]}-{isbn[9:12]}-{isbn[12:]}")

    for q in queries:
        url = f"https://didasko.cz/?s={q}&post_type=product"
        print(f"DEBUG: Didasko zkouší query: {q} (URL: {url})")
        try:
            async with session.get(url, timeout=10) as resp:
                print(f"DEBUG: Didasko status: {resp.status}, Final URL: {resp.url}")
                if resp.status != 200: continue
                text = await resp.text()
                
            final_url = str(resp.url)
            if "/obchod/" in final_url and final_url.strip("/").split("/")[-1] != "obchod":
                links = [final_url]
                print(f"DEBUG: Didasko nalezen přímý link: {final_url}")
            else:
                links = set(re.findall(r'href="(https://didasko.cz/obchod/[^/"]+/)"', text))
                links = [l for l in links if "feed" not in l and "page" not in l][:5]
                print(f"DEBUG: Didasko nalezeno linků: {len(links)}")
            
            for link in links:
                print(f"DEBUG: Didasko zkouší link: {link}")
                async with session.get(link, timeout=10) as resp:
                    if resp.status == 200:
                        ptext = await resp.text()
                        isbn_match = re.search(r'<li class="isbn[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                        if not isbn_match: 
                            print(f"DEBUG: Didasko link {link} nemá ISBN v HTML")
                            continue
                        found_isbn = re.sub(r'[- ]', '', isbn_match.group(1))
                        print(f"DEBUG: Didasko nalezeno ISBN: {found_isbn} (hledáno: {isbn})")
                        if found_isbn != isbn: continue
                        
                        return {"title": "Found", "url": link}
        except Exception as e:
            print(f"DEBUG: Didasko chyba při query {q}: {e}")
            continue
    return None

async def main():
    async with aiohttp.ClientSession() as session:
        res = await fetch_didasko_cz(session, "9788088447634")
        print(f"VÝSLEDEK: {res}")

if __name__ == "__main__":
    asyncio.run(main())
