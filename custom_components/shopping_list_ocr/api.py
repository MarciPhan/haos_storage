import os
import io
import json
import base64
import logging
import aiohttp
import re
import uuid
import time
from datetime import timedelta
import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Seznam klíčových slov pro detekci kategorií (pokud Gemini selže)
CATEGORIES = {
    "Ovoce a zelenina": ["jablko", "banán", "rajče", "okurka", "paprika", "brambor", "cibule", "česnek", "ovoce", "zelenina"],
    "Mléčné výrobky": ["mléko", "jogurt", "sýr", "tvaroh", "máslo", "smetana", "vejce", "eidam", "gouda", "mozzarella"],
    "Maso a ryby": ["maso", "kuřecí", "hovězí", "vepřové", "šunka", "salám", "párky", "ryba", "losos", "pstruh"],
    "Pečivo": ["rohlík", "chléb", "houska", "bageta", "kobliha", "koláč", "veka"],
    "Nápoje": ["voda", "džus", "pivo", "víno", "limonáda", "cola", "čaj", "káva", "minerálka"],
    "Drogerie": ["mýdlo", "šampon", "pasta", "kartáček", "toaletní", "papír", "prací", "aviváž"],
}

# Častá slova na účtenkách, která nejsou produkty
SKIP_WORDS = set([
    "SLEVA", "CELKEM", "KČ", "DPH", "ZAOKROUHLENÍ", "VČETNĚ", "HOTOVOST", "KARTOU", "PLATBA",
    "REKAPITULACE", "TRŽBA", "FIK", "BKP", "DIČO", "PRODEJ", "POKLADNA", "DĚKUJEME", "DATUM",
])

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _prepare_image(image_path: str, max_size_kb: int = 1000) -> tuple[str, str]:
    """Compress image and encode to base64."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        _LOGGER.error("Pillow library is required for image compression.")
        raise

    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
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

async def process_receipt_image(hass: HomeAssistant, image_path: str, gemini_key: str = "", ocr_space_key: str = "") -> dict:
    """Send an image to OCR and return parsed data (Gemini first, fallback to ocr.space)."""
    if not os.path.isfile(image_path):
        _LOGGER.error("Receipt image not found: %s", image_path)
        return {"items": []}

    if gemini_key:
        _LOGGER.info("Using Gemini for OCR")
        result = await process_receipt_with_gemini(hass, image_path, gemini_key)
        if result is not None:
            return result
        _LOGGER.warning("Gemini OCR failed entirely, falling back to ocr.space")

    return await process_receipt_with_ocr_space(hass, image_path, ocr_space_key)


async def process_receipt_with_gemini(hass: HomeAssistant, image_path: str, api_key: str) -> dict | None:
    """Use Gemini 1.5/2.0 Flash to extract full receipt data."""
    try:
        b64, mime = await hass.async_add_executor_job(_prepare_image, image_path, 2048)
        
        prompt = """Extrahuje data z této účtenky. Vrať čistý JSON objekt s touto přesnou strukturou:
{
  "store": "Název obchodu (např. Tesco, Lidl, Albert... pokud chybí, nech prázdné)",
  "date": "Datum nákupu ve formátu YYYY-MM-DDTHH:MM:SS (pokud chybí, nech prázdné)",
  "total": 182.97,
  "items": [
    {"name": "název produktu", "price": 12.90, "quantity": 1, "expiry_days": 7}
  ]
}
Důležité:
- Vrať POUZE JSON, žádný jiný text.
- U každé položky odhadni běžnou dobu trvanlivosti (expiry_days) ve dnech od nákupu (např. čerstvé pečivo 1, mléko 7, sýr 14, trvanlivé potraviny 180). Pokud nevíš, dej null.
- Ceny a počty musí být čísla. Ignoruj slevy/vratky a nesmyslné texty."""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}}
                ]
            }]
        }

        # Try multiple common model names and API versions
        configs = [
            ("v1beta", "gemini-1.5-flash"),
            ("v1", "gemini-1.5-flash"),
            ("v1beta", "gemini-1.5-flash-latest"),
            ("v1beta", "gemini-2.0-flash"),
        ]
        
        last_err = ""
        for ver, model_id in configs:
            url = f"https://generativelanguage.googleapis.com/{ver}/models/{model_id}:generateContent?key={api_key}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 404:
                            continue
                        if resp.status != 200:
                            last_err = f"API Error {resp.status} for {model_id}: {await resp.text()}"
                            continue
                        
                        result = await resp.json()
                        if 'candidates' not in result or not result['candidates']:
                            last_err = f"No candidates for {model_id}"
                            continue
                        
                        content = result['candidates'][0].get('content', {})
                        parts = content.get('parts', [])
                        if not parts:
                            last_err = f"No parts for {model_id}"
                            continue
                            
                        raw_text = parts[0].get('text', '')
                        
                        # Robust extraction
                        start = raw_text.find('{')
                        end = raw_text.rfind('}')
                        if start == -1 or end == -1 or end <= start:
                            last_err = f"No JSON in response for {model_id}. Raw: {raw_text}"
                            continue
                        
                        json_str = raw_text[start:end+1]
                        data = json.loads(json_str)
                        
                        def parse_num(v, is_int=False):
                            if v is None: return 0 if not is_int else 1
                            v_str = str(v).replace(',', '.').replace(' ', '').strip()
                            v_str = re.sub(r'[^\d.-]', '', v_str)
                            try:
                                return int(float(v_str)) if is_int else float(v_str)
                            except: return 0 if not is_int else 1

                        return {
                            "store": data.get("store", ""),
                            "date": data.get("date", ""),
                            "total": parse_num(data.get("total", 0)),
                            "items": [
                                {
                                    "name": str(i.get("name", "Položka")),
                                    "price": parse_num(i.get("price", 0)),
                                    "quantity": parse_num(i.get("quantity", 1), is_int=True),
                                    "expiry_days": i.get("expiry_days")
                                } for i in data.get("items", []) if isinstance(i, dict)
                            ],
                            "raw_text": raw_text
                        }
            except Exception as e:
                last_err = str(e)
                continue
                
        return {"items": [], "debug": f"All Gemini attempts failed.\nLast error: {last_err}"}
        
    except Exception as exc:
        import traceback
        _LOGGER.error("Gemini OCR request failed: %s", exc)
        return {"items": [], "debug": f"{str(exc)}\n\n{traceback.format_exc()}"}


async def process_receipt_with_ocr_space(hass: HomeAssistant, image_path: str, api_key: str) -> dict:
    """Send an image to OCR.space and return parsed data fallback."""
    try:
        b64, mime = await hass.async_add_executor_job(_prepare_image, image_path, 1024)
        key = api_key or "K84310118888957" # Default key if possible, but user should provide one
        
        payload = {
            "apikey": key,
            "language": "cze",
            "base64Image": f"data:{mime};base64,{b64}",
            "isOverlayRequired": False,
            "detectOrientation": True,
            "scale": True,
            "OCREngine": 2,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.ocr.space/parse/image", data=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    return {"items": []}
                result = await resp.json()
                
                text = ""
                if "ParsedResults" in result and result["ParsedResults"]:
                    text = result["ParsedResults"][0].get("ParsedText", "")
                
                return {
                    "items": _parse_receipt_text(text),
                    "raw_text": text
                }
    except Exception as exc:
        _LOGGER.error("OCR.space request failed: %s", exc)
        return {"items": []}


def _parse_receipt_text(text: str) -> list:
    """Fallback regex parser for OCR.space raw text."""
    items = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3: continue
        # Simple regex for "Item Name  Price"
        match = re.search(r'^(.*?)\s+((?:\d[\d\s]*[,.]\s*\d{1,2}|\d{1,4}))\s*(?:K[CcčČ]|CZK)?$', line)
        if match:
            name = match.group(1).strip()
            if any(w in name.upper() for w in SKIP_WORDS): continue
            price_str = match.group(2).replace(",", ".").replace(" ", "")
            try:
                price = float(price_str)
                items.append({"name": name, "price": price, "quantity": 1})
            except: pass
    return items

async def fetch_product_by_ean(hass: HomeAssistant, ean: str) -> dict | None:
    """Fetch product info from Open Food Facts."""
    url = f"https://world.openfoodfacts.org/api/v0/product/{ean}.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if data.get("status") != 1: return None
                p = data.get("product", {})
                return {
                    "name": p.get("product_name_cs") or p.get("product_name") or "Neznámý produkt",
                    "image_url": p.get("image_front_url", ""),
                    "category": p.get("categories", "").split(",")[0].strip(),
                    "brand": p.get("brands", ""),
                }
    except: return None
