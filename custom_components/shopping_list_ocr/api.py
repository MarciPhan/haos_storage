"""API helpers for Nákupník — OCR, recipe parsing, product lookup."""

import logging
import os
import re
import base64
import json
import io
import aiohttp
from bs4 import BeautifulSoup
from PIL import Image
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Lines on a receipt that should never be treated as products
_SKIP_WORDS = frozenset([
    "CELKEM", "SOUČET", "SOUCET", "PLATBA", "KARTOU", "HOTOVOST",
    "DPH", "BDP", "FIK", "PKP", "EET", "DIČ", "IČ", "IČO",
    "DIČO", "PRODEJ", "POKLADNA", "DĚKUJEME", "DATUM",
])

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _prepare_image(image_path: str, max_size_kb: int = 1024) -> tuple[str, str]:
    """Resize and compress image to stay under size limit. Returns (base64_data, mime_type)."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g. for PNG with transparency)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Resize if too large (standard receipts don't need 4K+)
            if max(img.size) > 2000:
                img.thumbnail((2000, 2000), Image.LANCZOS)
                
            quality = 85
            data = None
            while quality >= 20:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                if len(data) < max_size_kb * 1024:
                    break
                quality -= 15
                
            return base64.b64encode(data).decode(), "image/jpeg"
    except Exception as exc:
        _LOGGER.error("Image compression failed: %s", exc)
        # Fallback to raw file if compression fails
        with open(image_path, "rb") as f:
            ext = os.path.splitext(image_path)[1].lower().lstrip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
            return base64.b64encode(f.read()).decode(), f"image/{mime}"

# ---------------------------------------------------------------------------
#  OCR
# ---------------------------------------------------------------------------

async def process_receipt_image(hass: HomeAssistant, image_path: str, gemini_key: str = "", ocr_space_key: str = "") -> list[dict]:
    """Send an image to OCR and return parsed items (Gemini first, fallback to ocr.space)."""
    if not os.path.isfile(image_path):
        _LOGGER.error("Receipt image not found: %s", image_path)
        return []

    if gemini_key:
        _LOGGER.info("Using Gemini 1.5 Flash for OCR")
        items = await process_receipt_with_gemini(hass, image_path, gemini_key)
        if items:
            return items
        _LOGGER.warning("Gemini OCR failed or returned no items, falling back to ocr.space")

    return await process_receipt_with_ocr_space(hass, image_path, ocr_space_key)


async def process_receipt_with_gemini(hass: HomeAssistant, image_path: str, api_key: str) -> list[dict]:
    """Use Gemini 1.5 Flash to extract items and prices from a receipt."""
    b64, mime = await hass.async_add_executor_job(_prepare_image, image_path, 2048) # Gemini handles up to 2MB easily
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = """Extrahuje položky z této účtenky. Pro každou položku vrať JSON objekt se strukturou:
{"name": "název produktu", "price": 12.90, "quantity": 1}
Vrať pouze čistý seznam JSON objektů v poli, nic jiného. Ceny musí být čísla. Pokud je u položky počet kusů (např. 2x), nastav quantity. Ignoruj slevy/vratky."""

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": b64}}
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    _LOGGER.error("Gemini API error %d: %s", resp.status, err)
                    return []
                result = await resp.json()
                text = result['candidates'][0]['content']['parts'][0]['text']
                items = json.loads(text)
                if isinstance(items, list):
                    for item in items:
                        item["price"] = float(item.get("price", 0))
                        item["quantity"] = int(item.get("quantity", 1))
                    return items
    except Exception as exc:
        _LOGGER.error("Gemini OCR request failed: %s", exc)
    return []


async def process_receipt_with_ocr_space(hass: HomeAssistant, image_path: str, api_key: str) -> list[dict]:
    """Send an image to OCR.space and return parsed items."""
    # ocr.space free tier is limited to 1MB
    b64, mime = await hass.async_add_executor_job(_prepare_image, image_path, 1024)
    
    # Use default key if none provided
    key = api_key or ""
    
    payload = {
        "apikey": key,
        "language": "cze",
        "base64Image": f"data:{mime};base64,{b64}",
        "isOverlayRequired": False,
        "detectOrientation": True,
        "scale": True,
        "OCREngine": 2,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.ocr.space/parse/image",
                data=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("OCR.space API HTTP %d", resp.status)
                    return []
                result = await resp.json()
    except Exception as exc:
        _LOGGER.error("OCR.space request failed: %s", exc)
        return []

    if result.get("OCRExitCode") != 1:
        _LOGGER.error("OCR failed: %s", result.get("ErrorMessage"))
        return []

    raw = "\n".join(page.get("ParsedText", "") for page in result.get("ParsedResults", []))
    return _parse_receipt_text(raw)


def _parse_receipt_text(text: str) -> list[dict]:
    """Extract (name, price, quantity) tuples from OCR output."""
    items: list[dict] = []
    item_re = re.compile(r"^(.*?)\s+((?:\d[\d\s]*[,.]\s*\d{1,2}|\d{1,4}))\s*(?:K[CcčČ]|CZK|A|B|C|E|%)?\s*$", re.IGNORECASE)

    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4: continue
        if any(w in line.upper() for w in _SKIP_WORDS): continue

        m = item_re.match(line)
        if not m: continue

        name = m.group(1).strip()
        if len(name) < 3: continue
        name = re.sub(r"^\d+\s*[xX]\s*", "", name).strip()

        price_str = m.group(2).replace(" ", "").replace(",", ".")
        try:
            price = float(price_str)
            if price > 0:
                items.append({"name": name, "price": price, "quantity": 1})
        except ValueError:
            continue
    return items


# ---------------------------------------------------------------------------
#  EAN lookup (Open Food Facts)
# ---------------------------------------------------------------------------

async def fetch_product_by_ean(hass: HomeAssistant, ean: str) -> dict | None:
    """Query Open Food Facts for product info by EAN barcode."""
    url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
    headers = {"User-Agent": "HomeAssistant-Nakupnik/2.0"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200: return None
                body = await resp.json()
                if body.get("status") != 1: return None
                p = body.get("product", {})
                name = p.get("product_name_cs") or p.get("product_name") or "Neznámý produkt"
                brand = p.get("brands", "")
                if brand and brand.lower() not in name.lower():
                    name = f"{brand} – {name}"
                return {
                    "name": name,
                    "image_url": p.get("image_front_small_url") or p.get("image_url") or "",
                    "ean": ean,
                }
    except Exception:
        return None


# ---------------------------------------------------------------------------
#  Recipe fetching
# ---------------------------------------------------------------------------

async def fetch_recipe_content(hass: HomeAssistant, url: str) -> dict | None:
    """Scrape a recipe page and return structured data."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200: return None
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        recipe = {"title": soup.find("h1").get_text(strip=True) if soup.find("h1") else "Recept", "ingredients": [], "instructions": "", "url": url, "image_url": ""}
        
        # Meta image
        og = soup.find("meta", property="og:image")
        if og: recipe["image_url"] = og.get("content", "")

        # Site-specific
        domain = url.lower()
        if "toprecepty.cz" in domain:
            for el in soup.select(".recipe-ingredients__item, .recipe-ingredients li"): recipe["ingredients"].append(el.get_text(strip=True))
            inst = soup.select_one(".recipe-instructions, .postup")
            if inst: recipe["instructions"] = inst.get_text(strip=True)
        elif "madebykristina.cz" in domain:
            for el in soup.select(".suroviny-kika-obsah li"): recipe["ingredients"].append(el.get_text(strip=True))
            inst = soup.select_one(".postup-kika-obsah")
            if inst: recipe["instructions"] = inst.get_text(strip=True)
            
        # Fallback
        if not recipe["ingredients"]:
            for li in soup.find_all("li"):
                txt = li.get_text(strip=True)
                if txt and re.match(r"^\d", txt) and len(txt) < 150: recipe["ingredients"].append(txt)
        
        if not recipe["instructions"]:
            paras = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 80]
            recipe["instructions"] = "\n\n".join(paras[:10])
            
        return recipe
    except Exception:
        return None
