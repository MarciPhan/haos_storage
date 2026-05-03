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

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_RECEIPTS_UPDATED
from .api import (
    process_receipt_image,
    fetch_recipe_content,
    fetch_product_by_ean,
)

_LOGGER = logging.getLogger(__name__)

FONT_URL = "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts/ttf/DejaVuSans.ttf"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

async def _ensure_font(target_path: str) -> bool:
    """Download DejaVuSans.ttf if it doesn't exist locally."""
    if os.path.isfile(target_path):
        return True
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FONT_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    with open(target_path, "wb") as f:
                        f.write(await resp.read())
                    _LOGGER.info("Downloaded DejaVuSans font to %s", target_path)
                    return True
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
    for key in ("inventory", "pending_receipts", "recipes", "keep_config"):
        data.setdefault(key, {})

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    local_font = os.path.join(os.path.dirname(__file__), "www", "DejaVuSans.ttf")
    recipes_dir = os.path.join(os.path.dirname(__file__), "www", "recipes")
    os.makedirs(recipes_dir, exist_ok=True)

    # Pre-download font at startup (non-blocking)
    hass.async_create_task(_ensure_font(local_font))

    # -- helpers --
    async def _save():
        await store.async_save(data)
        hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    # -----------------------------------------------------------------------
    #  Services
    # -----------------------------------------------------------------------

    async def handle_scan_receipt(call: ServiceCall):
        """Scan a single receipt image via OCR."""
        image_path = call.data.get("image_path", "")
        if not image_path or not os.path.isfile(image_path):
            _LOGGER.error("Image not found: %s", image_path)
            return

        items = await process_receipt_image(hass, image_path)
        if not items:
            _LOGGER.warning("No items found on receipt: %s", image_path)
            return

        all_text = " ".join(i["name"] for i in items)
        store_name = _detect_store(all_text)

        receipt_id = str(uuid.uuid4())
        data["pending_receipts"][receipt_id] = {
            "id": receipt_id,
            "date": dt_util.now().isoformat(),
            "items": items,
            "image_path": image_path,
            "store": store_name,
        }
        await _save()
        _LOGGER.info("Scanned receipt %s: %d items (store=%s)", receipt_id, len(items), store_name)

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
            items = await process_receipt_image(hass, full)
            if items:
                all_text = " ".join(i["name"] for i in items)
                rid = str(uuid.uuid4())
                data["pending_receipts"][rid] = {
                    "id": rid,
                    "date": dt_util.now().isoformat(),
                    "items": items,
                    "image_path": full,
                    "store": _detect_store(all_text),
                }
                count += 1
        if count:
            await _save()
        _LOGGER.info("Folder scan complete: %d new receipts from %s", count, folder)

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
                data["inventory"][name] = {
                    "name": name,
                    "quantity": item.get("quantity", 1),
                    "last_price": item.get("price", 0),
                    "unit": item.get("unit", "ks"),
                    "min_quantity": 0,
                    "expiry_days": 0,
                    "image_url": item.get("image_url", ""),
                    "store": receipt.get("store"),
                }
        await _save()

    async def handle_update_inventory(call: ServiceCall):
        """Manually update or delete an inventory item."""
        name = call.data.get("name", "")
        if not name:
            return
        if call.data.get("action") == "delete":
            data["inventory"].pop(name, None)
        else:
            data["inventory"][name] = {
                "name": name,
                "quantity": call.data.get("quantity", 0),
                "last_price": call.data.get("last_price", 0),
                "unit": call.data.get("unit", "ks"),
                "min_quantity": call.data.get("min_quantity", 0),
                "expiry_days": call.data.get("expiry_days", 0),
                "image_url": call.data.get("image_url", ""),
                "store": call.data.get("store", ""),
            }
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
            data["inventory"][name] = {
                "name": name,
                "quantity": qty,
                "last_price": 0,
                "unit": "ks",
                "min_quantity": 0,
                "expiry_days": 0,
                "image_url": product.get("image_url") or "",
                "ean": ean,
                "store": "",
            }
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
            pdf = FPDF()
            pdf.add_page()

            font_path = _get_font_path(local_font)
            if font_path:
                pdf.add_font("DejaVu", "", font_path)
                font_name = "DejaVu"
            else:
                _LOGGER.warning("No Unicode font available; Czech characters may break")
                font_name = "Helvetica"

            # Title
            pdf.set_font(font_name, size=18)
            pdf.cell(190, 12, txt=recipe_data["title"], ln=True, align="C")
            pdf.ln(8)

            # Source
            if recipe_data.get("url"):
                pdf.set_font(font_name, size=9)
                pdf.cell(190, 6, txt=f"Zdroj: {recipe_data['url']}", ln=True, align="C")
                pdf.ln(8)

            # Ingredients
            pdf.set_font(font_name, size=14)
            pdf.cell(190, 10, txt="Ingredience:", ln=True)
            pdf.set_font(font_name, size=11)
            for ing in recipe_data.get("ingredients", []):
                pdf.multi_cell(180, 7, txt=f"  \u2022 {ing}")
            pdf.ln(6)

            # Instructions
            pdf.set_font(font_name, size=14)
            pdf.cell(190, 10, txt="Postup:", ln=True)
            pdf.set_font(font_name, size=11)
            pdf.multi_cell(190, 7, txt=recipe_data.get("instructions", ""))

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

    async def handle_sync_to_keep(call: ServiceCall):
        """Synchronise the HA shopping list to a Google Keep checklist."""
        import gkeepapi

        username = call.data.get("username") or data["keep_config"].get("username", "")
        password = call.data.get("password") or data["keep_config"].get("password", "")
        note_title = call.data.get("title") or data["keep_config"].get("title", "Nákup")

        if not username or not password:
            _LOGGER.error("Google Keep credentials not provided")
            return

        # Persist credentials for future use
        if call.data.get("username"):
            data["keep_config"] = {
                "username": username,
                "password": password,
                "title": note_title,
            }
            await store.async_save(data)

        def _sync():
            keep = gkeepapi.Keep()
            keep.login(username, password)

            # Find existing note or create new
            note = None
            for n in keep.find(archived=False, trashed=False):
                if n.title == note_title:
                    note = n
                    break
            if note is None:
                note = keep.createList(note_title)

            # Get items from HA shopping list
            sl = hass.data.get("shopping_list")
            items = []
            if sl:
                items = [i["name"] for i in sl.items if not i["complete"]]

            # Clear old items and add new
            for item in note.items:
                item.delete()
            for name in items:
                note.add(name, False)

            keep.sync()
            _LOGGER.info("Synced %d items to Google Keep note '%s'", len(items), note_title)

        try:
            await hass.async_add_executor_job(_sync)
        except Exception as exc:
            _LOGGER.error("Google Keep sync failed: %s", exc)

    # -----------------------------------------------------------------------
    #  Register everything
    # -----------------------------------------------------------------------

    svc = hass.services.async_register
    svc(DOMAIN, "scan_receipt", handle_scan_receipt)
    svc(DOMAIN, "scan_folder", handle_scan_folder)
    svc(DOMAIN, "confirm_receipt", handle_confirm_receipt)
    svc(DOMAIN, "update_inventory", handle_update_inventory)
    svc(DOMAIN, "add_item_by_ean", handle_add_item_by_ean)
    svc(DOMAIN, "add_recipe", handle_add_recipe)
    svc(DOMAIN, "sync_to_keep", handle_sync_to_keep)

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
