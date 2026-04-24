import asyncio
import aiohttp
import re

async def main():
    isbn = "9788090024069" # Let's see if they have Ryrie's teologie
    async with aiohttp.ClientSession() as session:
        url = f"https://didasko.cz/?s={isbn}&post_type=product"
        async with session.get(url, timeout=10) as resp:
            text = await resp.text()
            print("Status:", resp.status)
            
            # Find the product link from the search results
            match = re.search(r'<a href="(https://didasko.cz/obchod/[^"]+)"', text)
            if match:
                product_url = match.group(1)
                print("Found product:", product_url)
                
                # Fetch the product page
                async with session.get(product_url) as resp2:
                    p_text = await resp2.text()
                    
                    # Extract cover
                    cover_match = re.search(r'<meta property="og:image" content="([^"]+)"', p_text)
                    print("Cover:", cover_match.group(1) if cover_match else None)
                    
                    # Extract title
                    title_match = re.search(r'<h1 class="product_title entry-title">([^<]+)</h1>', p_text)
                    print("Title:", title_match.group(1) if title_match else None)
            else:
                print("Product not found via standard search. Checking if it redirected directly to the product.")
                if "product_title" in text:
                    print("Redirected to product directly.")
                    cover_match = re.search(r'<meta property="og:image" content="([^"]+)"', text)
                    print("Cover:", cover_match.group(1) if cover_match else None)
                    title_match = re.search(r'<h1 class="product_title entry-title">([^<]+)</h1>', text)
                    print("Title:", title_match.group(1) if title_match else None)
                    # Look for pages (Počet stran)
                    pages_match = re.search(r'Počet stran:.*?(\d+)', text, re.IGNORECASE | re.DOTALL)
                    print("Pages:", pages_match.group(1) if pages_match else None)

asyncio.run(main())
