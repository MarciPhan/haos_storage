import asyncio
import aiohttp
import re

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get("https://didasko.cz/obchod/dilo-krista/") as r2:
            pt = await r2.text()
            # WooCommerce uses sku for ISBN often
            sku_m = re.search(r'class="sku">([^<]+)<', pt)
            print("SKU:", sku_m.group(1) if sku_m else "None")
            
            # Attributes tab (Vlastnosti)
            attrs = re.findall(r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>', pt, re.DOTALL)
            for k, v in attrs:
                # Remove html tags
                v_clean = re.sub(r'<[^>]+>', '', v).strip()
                k_clean = k.strip()
                print(f"{k_clean}: {v_clean}")
                
            # Cover
            img_m = re.search(r'<meta property="og:image" content="([^"]+)"', pt)
            print("Image:", img_m.group(1) if img_m else "None")

asyncio.run(main())
