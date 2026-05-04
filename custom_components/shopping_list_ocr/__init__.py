"""Nákupník – Home Assistant integration for inventory, receipts, recipes & Google Keep sync."""

import logging
import os
import uuid
import time

import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.components.http import HomeAssistantView
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_RECEIPTS_UPDATED, CONF_GEMINI_KEY, CONF_OCR_SPACE_KEY
from .api import (
    process_receipt_image,
    fetch_recipe_content,
    fetch_product_by_ean,
)

_LOGGER = logging.getLogger(__name__)

FONT_URL = "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Me5Q.ttf"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

async def _ensure_font(target_path: str) -> bool:
    """Download Roboto-Regular.ttf if it doesn't exist locally."""
    if os.path.isfile(target_path):
        return True
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    urls = [
        FONT_URL,
        "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Regular.ttf"
    ]
    try:
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            with open(target_path, "wb") as f:
                                f.write(await resp.read())
                            _LOGGER.info("Downloaded Roboto font from %s to %s", url, target_path)
                            return True
                except Exception as inner_exc:
                    _LOGGER.debug("Failed to download font from %s: %s", url, inner_exc)
    except Exception as exc:
        _LOGGER.error("Failed to download font: %s", exc)
    return False


def _get_font_path(local_path: str) -> str | None:
    """Return the first available font path, or None."""
    candidates = [
        local_path,
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for fp in candidates:
        if os.path.isfile(fp):
            return fp
    return None


def _detect_store(text: str) -> str | None:
    """Heuristically detect which store the receipt came from."""
    lowered = text.lower()
    stores = {
        "tesco": "Tesco", "albert": "Albert", "lidl": "Lidl",
        "kaufland": "Kaufland", "billa": "Billa", "penny": "Penny",
        "globus": "Globus", "makro": "Makro", "coop": "COOP",
    }
    for key, name in stores.items():
        if key in lowered:
            return name
    return None


# ---------------------------------------------------------------------------
#  HTTP Views
# ---------------------------------------------------------------------------

class PanelJsView(HomeAssistantView):
    """Serve the frontend panel JavaScript."""
    url = "/shopping_list_static/panel.js"
    name = "api:shopping_list:panel"
    requires_auth = False

    async def get(self, request):
        from aiohttp import web
        path = os.path.join(os.path.dirname(__file__), "www", "panel.js")
        if not os.path.isfile(path):
            return web.Response(status=404, text="panel.js not found")
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})


class DataView(HomeAssistantView):
    """Serve the current data as JSON."""
    url = "/api/shopping_list/data"
    name = "api:shopping_list:data"
    requires_auth = True

    def __init__(self, data):
        self._data = data

    async def get(self, request):
        from aiohttp import web
        return web.json_response(self._data)


class UploadView(HomeAssistantView):
    """Accept receipt image uploads and trigger OCR."""
    url = "/api/shopping_list/upload"
    name = "api:shopping_list:upload"
    requires_auth = True

    def __init__(self, hass_ref, domain):
        self._hass = hass_ref
        self._domain = domain

    async def post(self, request):
        from aiohttp import web
        reader = await request.multipart()
        field = await reader.next()
        if field is None or field.name != "file":
            return web.json_response({"error": "No file field"}, status=400)

        filename = field.filename or "upload.jpg"
        upload_dir = "/config/www/uctenky/"
        os.makedirs(upload_dir, exist_ok=True)
        ts = dt_util.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(upload_dir, f"{ts}_{filename}")

        size = 0
        with open(dest, "wb") as out:
            while True:
                chunk = await field.read_chunk(8192)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)

        _LOGGER.info("Uploaded receipt %s (%d bytes)", dest, size)
        await self._hass.services.async_call(
            self._domain, "scan_receipt", {"image_path": dest}
        )
        return web.json_response({"success": True, "path": dest, "size": size})


class RecipePdfView(HomeAssistantView):
    """Serve generated recipe PDFs."""
    url = "/shopping_list_static/recipes/{recipe_id}.pdf"
    name = "api:shopping_list:recipe_pdf"
    requires_auth = False

    async def get(self, request, recipe_id):
        from aiohttp import web
        path = os.path.join(os.path.dirname(__file__), "www", "recipes", f"{recipe_id}.pdf")
        if not os.path.isfile(path):
            return web.Response(status=404, text="PDF not found")
        return web.FileResponse(path)


# ---------------------------------------------------------------------------
#  Setup
# ---------------------------------------------------------------------------

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component from configuration.yaml (no-op)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Nákupník from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    # Ensure all top-level keys exist
    for key in ("inventory", "pending_receipts", "recipes", "keep_config", "consumption_log", "meal_plan"):
        data.setdefault(key, {} if key not in ("consumption_log", "meal_plan") else [])

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    local_font = os.path.join(os.path.dirname(__file__), "www", "Roboto-Regular.ttf")
    recipes_dir = os.path.join(os.path.dirname(__file__), "www", "recipes")
    os.makedirs(recipes_dir, exist_ok=True)

    # Pre-download font at startup (non-blocking)
    hass.async_create_task(_ensure_font(local_font))

    # -- helpers --
    async def _save():
        await store.async_save(data)
        hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    def _make_item(name, **kw):
        """Create a canonical inventory item dict."""
        return {
            "name": name,
            "quantity": kw.get("quantity", 1),
            "last_price": kw.get("last_price", 0),
            "unit": kw.get("unit", "ks"),
            "min_quantity": kw.get("min_quantity", 0),
            "expiry_date": kw.get("expiry_date", ""),
            "category": kw.get("category", ""),
            "location": kw.get("location", ""),
            "image_url": kw.get("image_url", ""),
            "store": kw.get("store", ""),
            "ean": kw.get("ean", ""),
            "added_at": kw.get("added_at", dt_util.now().isoformat()),
        }

    # -----------------------------------------------------------------------
    #  Services
    # -----------------------------------------------------------------------

    async def handle_update_meal_plan(call: ServiceCall):
        """Add, update or delete a meal in the meal plan."""
        action = call.data.get("action", "add")
        meal_id = call.data.get("id")
        
        if action == "delete" and meal_id:
            data["meal_plan"] = [m for m in data["meal_plan"] if m.get("id") != meal_id]
        else:
            meal = {
                "id": meal_id or str(uuid.uuid4()),
                "date": call.data.get("date"),
                "recipe_id": call.data.get("recipe_id"),
                "portions": call.data.get("portions", 4),
                "type": call.data.get("type", "Oběd"),
            }
            if not meal["date"] or not meal["recipe_id"]:
                return
            
            if meal_id:
                # Update existing
                for i, m in enumerate(data["meal_plan"]):
                    if m.get("id") == meal_id:
                        data["meal_plan"][i] = meal
                        break
                else:
                    data["meal_plan"].append(meal)
            else:
                # Add new
                data["meal_plan"].append(meal)
                
        await _save()

    async def handle_scan_receipt(call: ServiceCall):
        """Scan a single receipt image via OCR."""
        image_path = call.data.get("image_path", "")
        if not image_path or not os.path.isfile(image_path):
            _LOGGER.error("Image not found: %s", image_path)
            return

        gemini_key = entry.data.get(CONF_GEMINI_KEY, "")
        ocr_key = entry.data.get(CONF_OCR_SPACE_KEY, "")
        items = await process_receipt_image(hass, image_path, gemini_key, ocr_key)
        
        # We save the receipt even if items list is empty, allowing for manual entry
        all_text = " ".join(i.get("name", "") for i in items) if items else ""
        store_name = _detect_store(all_text)

        receipt_id = str(uuid.uuid4())
        data["pending_receipts"][receipt_id] = {
            "id": receipt_id,
            "date": dt_util.now().isoformat(),
            "items": items or [],
            "image_path": image_path,
            "store": store_name,
        }
        await _save()
        _LOGGER.info("Saved receipt %s: %d items (store=%s)", receipt_id, len(items or []), store_name)

    async def handle_scan_folder(call: ServiceCall):
        """Scan all new images in a folder."""
        folder = call.data.get("folder_path") or "/config/www/uctenky/"
        if not os.path.isdir(folder):
            _LOGGER.warning("Folder does not exist: %s", folder)
            return

        known = {r.get("image_path") for r in data["pending_receipts"].values()}
        exts = (".jpg", ".jpeg", ".png", ".webp")
        count = 0
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith(exts):
                continue
            full = os.path.join(folder, fname)
            if full in known:
                continue
            gemini_key = entry.data.get(CONF_GEMINI_KEY, "")
            ocr_key = entry.data.get(CONF_OCR_SPACE_KEY, "")
            items = await process_receipt_image(hass, full, gemini_key, ocr_key)
            
            all_text = " ".join(i.get("name", "") for i in items) if items else ""
            rid = str(uuid.uuid4())
            data["pending_receipts"][rid] = {
                "id": rid,
                "date": dt_util.now().isoformat(),
                "items": items or [],
                "image_path": full,
                "store": _detect_store(all_text),
            }
            count += 1
        if count:
            await _save()
        _LOGGER.info("Folder scan complete: %d new receipts from %s", count, folder)

    async def handle_update_pending_receipt(call: ServiceCall):
        """Update items or store of a pending receipt."""
        rid = call.data.get("receipt_id", "")
        if rid not in data["pending_receipts"]:
            return
        
        if call.data.get("action") == "delete":
            data["pending_receipts"].pop(rid)
        else:
            if "items" in call.data:
                data["pending_receipts"][rid]["items"] = call.data["items"]
            if "store" in call.data:
                data["pending_receipts"][rid]["store"] = call.data["store"]
                
        await _save()

    async def handle_confirm_receipt(call: ServiceCall):
        """Move pending receipt items into inventory."""
        rid = call.data.get("receipt_id", "")
        receipt = data["pending_receipts"].pop(rid, None)
        if not receipt:
            return
        for item in receipt["items"]:
            name = item["name"]
            if name in data["inventory"]:
                data["inventory"][name]["quantity"] += item.get("quantity", 1)
                data["inventory"][name]["last_price"] = item.get("price", 0)
            else:
                data["inventory"][name] = _make_item(
                    name,
                    quantity=item.get("quantity", 1),
                    last_price=item.get("price", 0),
                    unit=item.get("unit", "ks"),
                    image_url=item.get("image_url", ""),
                    store=receipt.get("store", ""),
                )
        await _save()

    async def handle_update_inventory(call: ServiceCall):
        """Manually update or delete an inventory item."""
        name = call.data.get("name", "")
        if not name:
            return
        if call.data.get("action") == "delete":
            data["inventory"].pop(name, None)
        elif call.data.get("action") == "consume":
            # Log consumption and decrease quantity
            if name in data["inventory"]:
                amount = call.data.get("amount", 1)
                data["inventory"][name]["quantity"] = max(
                    0, data["inventory"][name]["quantity"] - amount
                )
                data["consumption_log"].append({
                    "name": name,
                    "amount": amount,
                    "date": dt_util.now().isoformat(),
                })
                # Keep log trimmed to last 200 entries
                data["consumption_log"] = data["consumption_log"][-200:]
        else:
            existing = data["inventory"].get(name, {})
            data["inventory"][name] = _make_item(
                name,
                quantity=call.data.get("quantity", existing.get("quantity", 0)),
                last_price=call.data.get("last_price", existing.get("last_price", 0)),
                unit=call.data.get("unit", existing.get("unit", "ks")),
                min_quantity=call.data.get("min_quantity", existing.get("min_quantity", 0)),
                expiry_date=call.data.get("expiry_date", existing.get("expiry_date", "")),
                category=call.data.get("category", existing.get("category", "")),
                location=call.data.get("location", existing.get("location", "")),
                image_url=call.data.get("image_url", existing.get("image_url", "")),
                store=call.data.get("store", existing.get("store", "")),
                ean=call.data.get("ean", existing.get("ean", "")),
                added_at=existing.get("added_at", dt_util.now().isoformat()),
            )
        await _save()

    async def handle_add_item_by_ean(call: ServiceCall):
        """Look up a product by EAN and add to inventory."""
        ean = call.data.get("ean", "").strip()
        if not ean:
            return
        product = await fetch_product_by_ean(hass, ean)
        if not product:
            _LOGGER.warning("EAN %s not found in Open Food Facts", ean)
            return
        name = product["name"]
        qty = call.data.get("quantity", 1)
        if name in data["inventory"]:
            data["inventory"][name]["quantity"] += qty
        else:
            data["inventory"][name] = _make_item(
                name,
                quantity=qty,
                image_url=product.get("image_url", ""),
                ean=ean,
            )
        await _save()
        _LOGGER.info("Added by EAN %s: %s", ean, name)

    async def handle_add_recipe(call: ServiceCall):
        """Fetch a recipe from URL, save data, and generate PDF."""
        url = call.data.get("url", "").strip()
        if not url:
            return
        recipe_data = await fetch_recipe_content(hass, url)
        if not recipe_data:
            _LOGGER.error("Failed to fetch recipe from %s", url)
            return

        recipe_id = str(uuid.uuid4())
        pdf_path = os.path.join(recipes_dir, f"{recipe_id}.pdf")

        # Ensure font is ready
        await _ensure_font(local_font)

        def _gen_pdf():
            from fpdf import FPDF
            import unicodedata
            pdf = FPDF()
            pdf.add_page()

            font_path = _get_font_path(local_font)
            if font_path:
                pdf.add_font("Roboto", "", font_path)
                font_name = "Roboto"
            else:
                _LOGGER.warning("No Unicode font available; stripping accents to prevent crash")
                font_name = "Helvetica"

            def sanitize(text):
                if font_name == "Roboto":
                    return text
                # Normalize and remove accents/unsupported chars for Helvetica
                return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").encode("ascii", "ignore").decode("ascii")

            # Title
            pdf.set_font(font_name, size=18)
            pdf.cell(190, 12, txt=sanitize(recipe_data["title"]), ln=True, align="C")
            pdf.ln(8)

            # Source
            if recipe_data.get("url"):
                pdf.set_font(font_name, size=9)
                pdf.cell(190, 6, txt=sanitize(f"Zdroj: {recipe_data['url']}"), ln=True, align="C")
                pdf.ln(8)

            # Ingredients
            pdf.set_font(font_name, size=14)
            pdf.set_x(10)
            pdf.cell(190, 10, txt=sanitize("Ingredience:"), ln=True)
            pdf.set_font(font_name, size=11)
            bullet = "\u2022" if font_name == "Roboto" else "-"
            for ing in recipe_data.get("ingredients", []):
                pdf.set_x(15)
                pdf.multi_cell(175, 6, txt=sanitize(f"{bullet} {ing}"))
                pdf.ln(1)
            pdf.ln(4)

            # Instructions
            pdf.set_font(font_name, size=14)
            pdf.set_x(10)
            pdf.cell(190, 10, txt=sanitize("Postup:"), ln=True)
            pdf.set_font(font_name, size=11)
            pdf.set_x(10)
            pdf.multi_cell(190, 7, txt=sanitize(recipe_data.get("instructions", "")))

            pdf.output(pdf_path)

        await hass.async_add_executor_job(_gen_pdf)

        data["recipes"][recipe_id] = {
            "id": recipe_id,
            "title": recipe_data["title"],
            "ingredients": recipe_data.get("ingredients", []),
            "instructions": recipe_data.get("instructions", ""),
            "url": recipe_data.get("url", url),
            "image_url": recipe_data.get("image_url", ""),
            "pdf_url": f"/shopping_list_static/recipes/{recipe_id}.pdf",
            "added_at": dt_util.now().isoformat(),
        }
        await _save()
        _LOGGER.info("Added recipe: %s", recipe_data["title"])

    # -----------------------------------------------------------------------
    #  Services
    # -----------------------------------------------------------------------

    svc = hass.services.async_register
    svc(DOMAIN, "scan_receipt", handle_scan_receipt)
    svc(DOMAIN, "scan_folder", handle_scan_folder)
    svc(DOMAIN, "confirm_receipt", handle_confirm_receipt)
    svc(DOMAIN, "update_pending_receipt", handle_update_pending_receipt)
    svc(DOMAIN, "update_inventory", handle_update_inventory)
    svc(DOMAIN, "add_item_by_ean", handle_add_item_by_ean)
    svc(DOMAIN, "add_recipe", handle_add_recipe)
    svc(DOMAIN, "update_meal_plan", handle_update_meal_plan)

    hass.http.register_view(PanelJsView())
    hass.http.register_view(DataView(data))
    hass.http.register_view(UploadView(hass, DOMAIN))
    hass.http.register_view(RecipePdfView())

    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Nákupník",
            sidebar_icon="mdi:cart-outline",
            frontend_url_path="shopping-list-ocr",
            config={
                "_panel_custom": {
                    "name": "shopping-list-panel",
                    "module_url": f"/shopping_list_static/panel.js?v={int(time.time())}",
                }
            },
            require_admin=False,
        )
    except Exception as exc:
        _LOGGER.error("Failed to register panel: %s", exc)

    return True
