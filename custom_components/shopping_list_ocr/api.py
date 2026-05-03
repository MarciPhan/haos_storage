import logging
import re
import os
import easyocr
import numpy as np
from PIL import Image
import aiohttp
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Cache pro EasyOCR reader, aby se nenačítal při každém skenování
_READER = None

async def get_reader():
    """Get or create the EasyOCR reader."""
    global _READER
    if _READER is None:
        # Podporujeme češtinu a angličtinu
        # Při prvním spuštění si to stáhne modely (cca 100MB)
        _READER = easyocr.Reader(['cs', 'en'], gpu=False)
    return _READER

async def process_receipt_image(hass: HomeAssistant, image_path: str) -> list:
    """Extract items and prices from a receipt image using EasyOCR."""
    
    def perform_ocr():
        try:
            import asyncio
            # Spustíme reader v executoru
            reader = easyocr.Reader(['cs', 'en'], gpu=False)
            results = reader.readtext(image_path)
            return results
        except Exception as e:
            _LOGGER.error("EasyOCR Error: %s", e)
            return []

    # Použijeme executor, protože easyocr je CPU intenzivní a blokující
    results = await hass.async_add_executor_job(perform_ocr)
    if not results:
        return []

    return parse_easyocr_results(results)

def parse_easyocr_results(results: list) -> list:
    """Parse EasyOCR results into a list of items and prices.
    Results is a list of tuples: (bbox, text, confidence)
    """
    items = []
    
    # Sloučíme text do řádků na základě y-souřadnice bboxu
    # EasyOCR vrací jednotlivá slova/bloky, musíme je dát k sobě
    lines = []
    current_line = []
    last_y = -1
    threshold = 10 # Tolerance pro stejný řádek v pixelech
    
    # Seřadíme výsledky podle y-souřadnice horního levého rohu
    sorted_results = sorted(results, key=lambda x: x[0][0][1])
    
    for (bbox, text, prob) in sorted_results:
        y = bbox[0][1]
        if last_y == -1 or abs(y - last_y) <= threshold:
            current_line.append((bbox[0][0], text)) # (x, text)
        else:
            # Nový řádek - seřadíme ten starý podle x a spojíme ho
            current_line.sort(key=lambda x: x[0])
            lines.append(" ".join([t[1] for t in current_line]))
            current_line = [(bbox[0][0], text)]
        last_y = y
        
    if current_line:
        current_line.sort(key=lambda x: x[0])
        lines.append(" ".join([t[1] for t in current_line]))

    # Regex pro vyhledání ceny
    price_pattern = re.compile(r'(\d+[\.,]\s*\d{2})\s*(?:Kč|Kc|CZK)?\s*$', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        match = price_pattern.search(line)
        if match:
            price_str = match.group(1).replace(',', '.').replace(' ', '')
            try:
                price = float(price_str)
                name = line[:match.start()].strip()
                name = re.sub(r'^[*.\s-]+', '', name)
                
                if name and len(name) > 2:
                    items.append({
                        "name": name,
                        "price": price,
                        "quantity": 1,
                        "unit": "ks"
                    })
            except ValueError:
                continue
                
    return items

async def fetch_recipe_content(hass: HomeAssistant, url: str) -> dict | None:
    """Fetch and parse recipe from a URL."""
    try:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(hass)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with session.get(url, headers=headers, timeout=15, allow_redirects=True) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to fetch recipe from %s: %s", url, resp.status)
                return None
            html = await resp.text()
            final_url = str(resp.url)

        soup = BeautifulSoup(html, 'html.parser')
        
        recipe = {
            "title": "",
            "ingredients": [],
            "instructions": "",
            "url": final_url,
            "source": ""
        }

        # 1. Title
        title_tag = soup.find('h1')
        if title_tag:
            recipe["title"] = title_tag.get_text().strip()
        else:
            recipe["title"] = soup.title.string.split('|')[0].strip() if soup.title else "Recept"

        # 2. Specific scrapers
        if "toprecepty.cz" in final_url:
            recipe["source"] = "Toprecepty.cz"
            # Ingredients
            ing_list = soup.find('ul', class_='ingredients-list')
            if not ing_list:
                ing_list = soup.find('div', class_='recept-ingredience')
            
            if ing_list:
                for li in ing_list.find_all('li'):
                    text = li.get_text().strip()
                    if text:
                        recipe["ingredients"].append(text)
            
            # Instructions
            postup = soup.find('div', class_='postup')
            if postup:
                recipe["instructions"] = postup.get_text().strip()

        elif "madebykristina.cz" in final_url:
            recipe["source"] = "Made by Kristina"
            # Ingredients
            suroviny_h2 = soup.find('h2', string=re.compile(r'Suroviny', re.I))
            if suroviny_h2:
                ul = suroviny_h2.find_next('ul')
                if ul:
                    for li in ul.find_all('li'):
                        recipe["ingredients"].append(li.get_text().strip())
            
            # Instructions
            postup_h2 = soup.find('h2', string=re.compile(r'Postup', re.I))
            if postup_h2:
                curr = postup_h2.find_next()
                while curr and curr.name != 'h2':
                    if curr.name in ['p', 'ol', 'ul']:
                        recipe["instructions"] += curr.get_text().strip() + "\n\n"
                    curr = curr.find_next_sibling()

        elif "recepty.cz" in final_url:
            recipe["source"] = "Recepty.cz"
            ing_div = soup.find('div', class_='ingredients')
            if ing_div:
                for li in ing_div.find_all('li'):
                    recipe["ingredients"].append(li.get_text().strip())
            
            postup_div = soup.find('div', class_='preparation-process')
            if postup_div:
                recipe["instructions"] = postup_div.get_text().strip()

        # Generic fallback
        if not recipe["ingredients"]:
            # Try to find any list that looks like ingredients
            for ul in soup.find_all('ul'):
                if any(word in (ul.get('class') or []) for word in ['ingredients', 'suroviny', 'ingredience']):
                    for li in ul.find_all('li'):
                        recipe["ingredients"].append(li.get_text().strip())
                    break
        
        if not recipe["instructions"]:
            for div in soup.find_all(['div', 'section']):
                if any(word in (div.get('class') or []) for word in ['instructions', 'postup', 'preparation']):
                    recipe["instructions"] = div.get_text().strip()
                    break

        return recipe

    except Exception as e:
        _LOGGER.error("Error parsing recipe from %s: %s", url, e)
        return None
