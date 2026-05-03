import logging
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant
import re
import os
import base64

_LOGGER = logging.getLogger(__name__)

# OCR.space API Free Key - for testing purposes
# User should ideally get their own at ocr.space/ocrapi
OCR_API_KEY = "[REDACTED]" 

async def process_receipt_image(hass: HomeAssistant, image_path: str):
    """Scan a receipt using OCR.space API (Lightweight alternative)."""
    try:
        if not os.path.exists(image_path):
            _LOGGER.error("Image file %s not found", image_path)
            return []

        # Read and encode image to base64
        with open(image_path, "rb") as f:
            img_data = f.read()
            base64_img = base64.b64encode(img_data).decode("utf-8")

        _LOGGER.info("Sending receipt to OCR.space API...")
        
        url = "https://api.ocr.space/parse/image"
        payload = {
            "apikey": OCR_API_KEY,
            "language": "cze",
            "base64Image": f"data:image/jpeg;base64,{base64_img}",
            "isOverlayRequired": False,
            "FileType": ".jpg",
            "detectOrientation": True,
            "scale": True,
            "OCREngine": 2 # Engine 2 is better for table-like structures
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload, timeout=30) as response:
                if response.status != 200:
                    _LOGGER.error("OCR API error: %d", response.status)
                    return []
                
                result = await response.json()
                
                if result.get("OCRExitCode") != 1:
                    _LOGGER.error("OCR API failed: %s", result.get("ErrorMessage"))
                    return []

                parsed_text = ""
                for page in result.get("ParsedResults", []):
                    parsed_text += page.get("ParsedText", "") + "\n"

                _LOGGER.debug("Raw OCR text: %s", parsed_text)
                return parse_receipt_text(parsed_text)

    except Exception as e:
        _LOGGER.error("Error during OCR processing: %s", e)
        return []

def parse_receipt_text(text):
    """Extract items and prices from raw OCR text."""
    items = []
    lines = text.split('\n')
    
    # Common receipt patterns: ITEM NAME ... PRICE
    # Example: "BRAMBORY 1kg 25.90" or "CHLEBA 34,00"
    item_pattern = re.compile(r'(.+?)\s+([\d\s,.]+)[\sA-Z]*$')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3: continue
        
        # Skip common non-item lines
        if any(x in line.upper() for x in ["CELKEM", "SOUCET", "PLATBA", "KARTOU", "DPH", "BDP", "FIK", "PKP"]):
            continue
            
        match = item_pattern.search(line)
        if match:
            name = match.group(1).strip()
            price_str = match.group(2).replace(',', '.').replace(' ', '')
            try:
                price = float(price_str)
                if price > 0:
                    items.append({
                        "name": name,
                        "price": price,
                        "quantity": 1
                    })
            except ValueError:
                continue
                
    return items

async def fetch_recipe_content(hass: HomeAssistant, url: str):
    """Fetch recipe content from a URL using BeautifulSoup."""
    try:
        # Resolve share.google redirects if needed
        final_url = url
        if "share.google" in url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as resp:
                    final_url = str(resp.url)

        async with aiohttp.ClientSession() as session:
            async with session.get(final_url, timeout=10) as response:
                if response.status != 200:
                    return None
                html = await response.text()

        soup = BeautifulSoup(html, 'html.parser')
        
        recipe = {
            "title": "",
            "ingredients": [],
            "instructions": "",
            "url": final_url,
            "source": "",
            "image_url": ""
        }

        # 1. Title
        title_tag = soup.find('h1')
        if title_tag:
            recipe["title"] = title_tag.get_text().strip()
        else:
            recipe["title"] = soup.title.string.split('|')[0].strip() if soup.title else "Recept"

        # 1b. Image (og:image)
        og_image = soup.find('meta', property='og:image')
        if og_image:
            recipe["image_url"] = og_image.get('content')
        else:
            # Fallback to first large image
            for img in soup.find_all('img'):
                if img.get('src') and ('recipe' in img.get('src') or 'recept' in img.get('src')):
                    recipe["image_url"] = img.get('src')
                    break

        # 2. Specific scrapers
        if "toprecepty.cz" in final_url:
            recipe["source"] = "Toprecepty.cz"
            for ing in soup.select('.recipe-ingredients__item'):
                recipe["ingredients"].append(ing.get_text().strip())
            instructions = soup.select_one('.recipe-instructions')
            if instructions:
                recipe["instructions"] = instructions.get_text().strip()

        elif "madebykristina.cz" in final_url:
            recipe["source"] = "Made by Kristina"
            for ing in soup.select('.ingredient-list li'):
                recipe["ingredients"].append(ing.get_text().strip())
            instructions = soup.select_one('.recipe-method')
            if instructions:
                recipe["instructions"] = instructions.get_text().strip()
                
        elif "recepty.cz" in final_url:
            recipe["source"] = "Recepty.cz"
            for ing in soup.select('.ingredients-list li'):
                recipe["ingredients"].append(ing.get_text().strip())
            instructions = soup.select_one('.postup-text')
            if instructions:
                recipe["instructions"] = instructions.get_text().strip()
        
        # General fallback if no specific scraper matched
        if not recipe["ingredients"]:
            # Try to find common structures
            for li in soup.find_all('li'):
                text = li.get_text().strip()
                # Simple heuristic for ingredients (start with number or common units)
                if re.match(r'^\d+|^\d+[\s\w]*\s(g|kg|ml|l|ks|lžíce|lžička)', text):
                    recipe["ingredients"].append(text)
        
        if not recipe["instructions"]:
            # Look for large text blocks
            for p in soup.find_all('p'):
                if len(p.get_text()) > 100:
                    recipe["instructions"] += p.get_text().strip() + "\n\n"

        return recipe

    except Exception as e:
        _LOGGER.error("Error parsing recipe from %s: %s", url, e)
        return None

async def find_product_image(hass: HomeAssistant, product_name: str, store: str = None) -> str:
    """Try to find an image for a product, optionally scoped by store."""
    try:
        if store and store.lower() == "tesco":
            return f"https://nakup.itesco.cz/groceries/cs-CZ/search?query={product_name}"
        return f"https://www.google.com/search?q={product_name}&tbm=isch"
    except:
        return ""
