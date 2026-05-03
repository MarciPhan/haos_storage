"""API helpers for Nákupník — OCR, recipe parsing, product lookup."""

import logging
import os
import re
import base64

import aiohttp
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  OCR (ocr.space)
# ---------------------------------------------------------------------------

# Free demo key — users should register at https://ocr.space/ocrapi
# and replace this with their own key for reliable usage.
OCR_API_KEY = "K81234567888957"

# Lines on a receipt that should never be treated as products
_SKIP_WORDS = frozenset([
    "CELKEM", "SOUČET", "SOUCET", "PLATBA", "KARTOU", "HOTOVOST",
    "DPH", "BDP", "FIK", "PKP", "EET", "DIČ", "IČ", "IČO",
    "DIČO", "PRODEJ", "POKLADNA", "DĚKUJEME", "DATUM",
])

_ITEM_RE = re.compile(
    r"^(.{3,}?)\s+([\d][\d\s,.]*)\s*(?:Kč|CZK|A|B|C)?\s*$"
)


async def process_receipt_image(hass: HomeAssistant, image_path: str) -> list[dict]:
    """Send an image to OCR.space and return parsed items."""
    if not os.path.isfile(image_path):
        _LOGGER.error("Receipt image not found: %s", image_path)
        return []

    # Read file and encode; detect MIME type from extension
    ext = os.path.splitext(image_path)[1].lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(
        ext.lstrip("."), "jpeg"
    )

    def _read():
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    b64 = await hass.async_add_executor_job(_read)

    payload = {
        "apikey": OCR_API_KEY,
        "language": "cze",
        "base64Image": f"data:image/{mime};base64,{b64}",
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
                    _LOGGER.error("OCR API HTTP %d", resp.status)
                    return []
                result = await resp.json()
    except Exception as exc:
        _LOGGER.error("OCR request failed: %s", exc)
        return []

    if result.get("OCRExitCode") != 1:
        _LOGGER.error(
            "OCR failed (code %s): %s",
            result.get("OCRExitCode"),
            result.get("ErrorMessage"),
        )
        return []

    raw = "\n".join(
        page.get("ParsedText", "")
        for page in result.get("ParsedResults", [])
    )
    _LOGGER.debug("OCR raw text:\n%s", raw)
    return _parse_receipt_text(raw)


def _parse_receipt_text(text: str) -> list[dict]:
    """Extract (name, price, quantity) tuples from OCR output."""
    items: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        upper = line.upper()
        if any(w in upper for w in _SKIP_WORDS):
            continue

        m = _ITEM_RE.match(line)
        if not m:
            continue

        name = m.group(1).strip()
        price_str = m.group(2).replace(" ", "").replace(",", ".")
        try:
            price = float(price_str)
        except ValueError:
            continue
        if price <= 0:
            continue

        items.append({"name": name, "price": price, "quantity": 1})
    return items


# ---------------------------------------------------------------------------
#  EAN lookup (Open Food Facts)
# ---------------------------------------------------------------------------

_OFF_HEADERS = {"User-Agent": "HomeAssistant-Nakupnik/2.0 (contact@example.com)"}


async def fetch_product_by_ean(hass: HomeAssistant, ean: str) -> dict | None:
    """Query Open Food Facts for product info by EAN barcode."""
    url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
    try:
        async with aiohttp.ClientSession(headers=_OFF_HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return None
                body = await resp.json()
    except Exception as exc:
        _LOGGER.error("Open Food Facts request failed for EAN %s: %s", ean, exc)
        return None

    if body.get("status") != 1:
        return None

    p = body.get("product", {})
    name = (
        p.get("product_name_cs")
        or p.get("product_name")
        or p.get("generic_name_cs")
        or p.get("generic_name")
        or "Neznámý produkt"
    )
    brand = p.get("brands", "")
    if brand and brand.lower() not in name.lower():
        name = f"{brand} – {name}"

    return {
        "name": name,
        "image_url": p.get("image_front_small_url")
                     or p.get("image_front_url")
                     or p.get("image_url")
                     or "",
        "ean": ean,
    }


# ---------------------------------------------------------------------------
#  Recipe fetching
# ---------------------------------------------------------------------------

async def fetch_recipe_content(hass: HomeAssistant, url: str) -> dict | None:
    """Scrape a recipe page and return structured data."""
    try:
        final_url = url
        # Resolve Google share redirects
        if "share.google" in url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as resp:
                    final_url = str(resp.url)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                final_url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Recipe fetch HTTP %d for %s", resp.status, final_url)
                    return None
                html = await resp.text()
    except Exception as exc:
        _LOGGER.error("Recipe fetch failed: %s", exc)
        return None

    soup = BeautifulSoup(html, "html.parser")

    recipe: dict = {
        "title": "",
        "ingredients": [],
        "instructions": "",
        "url": final_url,
        "image_url": "",
    }

    # --- Title ---
    h1 = soup.find("h1")
    if h1:
        recipe["title"] = h1.get_text(strip=True)
    elif soup.title:
        recipe["title"] = soup.title.string.split("|")[0].strip()
    else:
        recipe["title"] = "Recept"

    # --- Image (og:image) ---
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        recipe["image_url"] = og["content"]

    # --- Site-specific scrapers ---
    domain = final_url.lower()

    if "toprecepty.cz" in domain:
        for el in soup.select(".recipe-ingredients__item, .recipe-ingredients li"):
            recipe["ingredients"].append(el.get_text(strip=True))
        inst = soup.select_one(".recipe-instructions, .postup")
        if inst:
            recipe["instructions"] = inst.get_text(strip=True)

    elif "recepty.cz" in domain:
        for el in soup.select(".ingredients-list li, .ingredient"):
            recipe["ingredients"].append(el.get_text(strip=True))
        inst = soup.select_one(".postup-text, .recipe-procedure")
        if inst:
            recipe["instructions"] = inst.get_text(strip=True)

    elif "vareni.cz" in domain:
        for el in soup.select(".ingredients li"):
            recipe["ingredients"].append(el.get_text(strip=True))
        inst = soup.select_one(".preparation")
        if inst:
            recipe["instructions"] = inst.get_text(strip=True)

    # --- Fallback: generic extraction ---
    if not recipe["ingredients"]:
        for li in soup.find_all("li"):
            txt = li.get_text(strip=True)
            if txt and re.match(r"^\d", txt) and len(txt) < 200:
                recipe["ingredients"].append(txt)

    if not recipe["instructions"]:
        paras = []
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 80:
                paras.append(txt)
        recipe["instructions"] = "\n\n".join(paras[:10])

    return recipe
