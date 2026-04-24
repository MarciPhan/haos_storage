import asyncio
import aiohttp
import re

async def fetch_didasko_cz(session, isbn: str) -> dict | None:
    # 1. Najít potenciální produkty
    url = f"https://didasko.cz/?s={isbn}&post_type=product"
    async with session.get(url, timeout=10) as resp:
        if resp.status != 200: return None
        text = await resp.text()
        
    links = set(re.findall(r'href="(https://didasko.cz/obchod/[^/"]+/)"', text))
    links = [l for l in links if "feed" not in l and "page" not in l][:5] # zkusíme max 5 výsledků
    
    # 2. Najít ten správný s přesným ISBN
    for link in links:
        async with session.get(link, timeout=10) as resp:
            if resp.status == 200:
                ptext = await resp.text()
                
                # Kontrola ISBN
                isbn_match = re.search(r'<li class="isbn[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                if not isbn_match:
                    continue
                
                found_isbn = re.sub(r'[- ]', '', isbn_match.group(1))
                if found_isbn != isbn:
                    continue
                
                # MÁme správný produkt!
                title_match = re.search(r'<meta property="og:title" content="([^"]+)"', ptext)
                title = title_match.group(1).replace(" - Didasko", "").strip() if title_match else None
                
                img_match = re.search(r'<meta property="og:image" content="([^"]+)"', ptext)
                cover_url = img_match.group(1) if img_match else None
                
                author_match = re.search(r'<li class="autor[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                author = author_match.group(1).strip() if author_match else None
                
                pages_match = re.search(r'<li class="pocet-stran[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                pages = int(pages_match.group(1)) if pages_match else None
                
                year_match = re.search(r'<li class="rok-vydani[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                year = year_match.group(1).strip() if year_match else None
                
                pub_match = re.search(r'<li class="vydavatel[^>]+>.*?<span class="attribute-value">([^<]+)</span>', ptext, re.IGNORECASE | re.DOTALL)
                publisher = pub_match.group(1).strip() if pub_match else None
                
                return {
                    "title": title,
                    "authors": [author] if author else [],
                    "cover_url": cover_url,
                    "pages": pages,
                    "publish_date": year,
                    "publishers": [publisher] if publisher else [],
                    "url": link
                }
    return None

async def main():
    async with aiohttp.ClientSession() as s:
        res = await fetch_didasko_cz(s, "9788087587089")
        print(res)

asyncio.run(main())
