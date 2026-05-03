import logging
import os
import uuid
import datetime
import re
import aiohttp
import time
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.components.http import HomeAssistantView
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_RECEIPTS_UPDATED
from .api import process_receipt_image, fetch_recipe_content, find_product_image, fetch_product_by_ean

_LOGGER = logging.getLogger(__name__)

async def download_font(hass: HomeAssistant, target_path: str):
    url = "https://github.com/mzyy94/DejaVuSans.ttf/raw/master/DejaVuSans.ttf"
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(target_path, "wb") as f: f.write(content)
                    return True
    except: pass
    return False

class ShoppingListPanelView(HomeAssistantView):
    url = "/shopping_list_static/panel.js"
    name = "api:shopping_list:panel"
    requires_auth = False
    async def get(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "www", "panel.js")
        from aiohttp import web
        return web.FileResponse(file_path)

class ShoppingListDataView(HomeAssistantView):
    url = "/api/shopping_list/data"
    name = "api:shopping_list:data"
    requires_auth = True
    def __init__(self, data): self._data = data
    async def get(self, request):
        from aiohttp import web
        return web.json_response(self._data)

class ShoppingListUploadView(HomeAssistantView):
    url = "/api/shopping_list/upload"
    name = "api:shopping_list:upload"
    requires_auth = True
    async def post(self, request):
        from aiohttp import web
        data = await request.post(); file = data.get("file")
        if not file: return web.json_response({"error": "No file"}, status=400)
        folder_path = "/config/www/uctenky/"; os.makedirs(folder_path, exist_ok=True)
        filename = f"upload_{dt_util.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "wb") as f: f.write(file.file.read())
        hass = request.app["hass"]
        await hass.services.async_call(DOMAIN, "scan_receipt", {"image_path": file_path})
        return web.json_response({"success": True})

class RecipePdfView(HomeAssistantView):
    url = "/shopping_list_static/recipes/{recipe_id}.pdf"
    name = "api:shopping_list:recipe_pdf"
    requires_auth = False
    async def get(self, request, recipe_id):
        file_path = os.path.join(os.path.dirname(__file__), "www", "recipes", f"{recipe_id}.pdf")
        from aiohttp import web
        return web.FileResponse(file_path)

async def async_setup_entry(hass: HomeAssistant, entry):
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {"inventory": {}, "pending_receipts": {}, "recipes": {}, "keep_config": {}}
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data
    local_font_path = os.path.join(os.path.dirname(__file__), "www", "DejaVuSans.ttf")

    async def handle_scan_receipt(call: ServiceCall):
        image_path = call.data.get("image_path")
        items = await process_receipt_image(hass, image_path)
        if items:
            all_text = " ".join([i["name"] for i in items]).lower()
            store_name = None
            for s in ["tesco", "albert", "lidl", "kaufland", "billa", "penny"]:
                if s in all_text: store_name = s.capitalize(); break
            for item in items: item["image_url"] = await find_product_image(hass, item["name"], store_name)
            receipt_id = str(uuid.uuid4())
            data["pending_receipts"][receipt_id] = {
                "id": receipt_id, "date": dt_util.now().isoformat(), "items": items, "image_path": image_path, "store": store_name
            }
            await store.async_save(data); hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_scan_folder(call: ServiceCall):
        folder_path = call.data.get("folder_path") or "/config/www/uctenky/"
        if not os.path.isdir(folder_path): return
        found_new = False
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                image_path = os.path.join(folder_path, filename)
                if any(r.get("image_path") == image_path for r in data["pending_receipts"].values()): continue
                await handle_scan_receipt(ServiceCall(DOMAIN, "scan_receipt", {"image_path": image_path}))
                found_new = True
        if found_new: await store.async_save(data); hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_confirm_receipt(call: ServiceCall):
        receipt_id = call.data.get("receipt_id")
        if receipt_id in data["pending_receipts"]:
            receipt = data["pending_receipts"].pop(receipt_id)
            for item in receipt["items"]:
                name = item["name"]
                if name in data["inventory"]:
                    data["inventory"][name]["quantity"] += item["quantity"]
                    data["inventory"][name]["last_price"] = item["price"]
                else:
                    data["inventory"][name] = {
                        "name": name, "quantity": item["quantity"], "last_price": item["price"],
                        "unit": item.get("unit", "ks"), "min_quantity": 0, "expiry_days": 0,
                        "image_url": item.get("image_url", ""), "store": receipt.get("store")
                    }
            await store.async_save(data); hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_add_item_by_ean(call: ServiceCall):
        ean = call.data.get("ean")
        product = await fetch_product_by_ean(hass, ean)
        if product:
            name = product["name"]
            if name in data["inventory"]: data["inventory"][name]["quantity"] += 1
            else:
                data["inventory"][name] = {
                    "name": name, "quantity": 1, "last_price": 0, "unit": "ks",
                    "min_quantity": 0, "expiry_days": 0, "image_url": product["image_url"], "ean": ean
                }
            await store.async_save(data); hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_sync_to_keep(call: ServiceCall):
        import gkeepapi
        username = call.data.get("username") or data["keep_config"].get("username")
        password = call.data.get("password") or data["keep_config"].get("password")
        note_title = call.data.get("title") or data["keep_config"].get("title") or "Nákup"
        if not username or not password: return
        if call.data.get("username"):
            data["keep_config"] = {"username": username, "password": password, "title": note_title}
            await store.async_save(data)
        def sync():
            keep = gkeepapi.Keep()
            try:
                keep.login(username, password)
                note = next((n for n in keep.find(archived=False, trashed=False) if n.title == note_title), None)
                if not note: note = keep.createList(note_title)
                sl_items = hass.data.get("shopping_list")
                items_to_add = [item["name"] for item in sl_items.items if not item["complete"]] if sl_items else []
                for item in note.items: item.delete()
                for item_name in items_to_add: note.add(item_name, False)
                keep.sync(); return True
            except: return False
        await hass.async_add_executor_job(sync)

    async def handle_add_recipe(call: ServiceCall):
        url = call.data.get("url")
        recipe_data = await fetch_recipe_content(hass, url)
        if not recipe_data: return
        recipe_id = str(uuid.uuid4()); pdf_path = os.path.join(os.path.dirname(__file__), "www", "recipes", f"{recipe_id}.pdf")
        if not os.path.exists(local_font_path): await download_font(hass, local_font_path)
        def generate_pdf():
            from fpdf import FPDF
            pdf = FPDF(); pdf.add_page(); font_loaded = False
            test_paths = [local_font_path, "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
            for fp in test_paths:
                if os.path.exists(fp):
                    try: pdf.add_font("DejaVu", "", fp); pdf.set_font("DejaVu", size=16); font_loaded = True; break
                    except: pass
            if not font_loaded: pdf.set_font("Helvetica", style="B", size=16)
            pdf.cell(190, 10, txt=recipe_data["title"], ln=True, align='C'); pdf.ln(10)
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=14)
            pdf.cell(190, 10, txt="Ingredience:", ln=True); pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=12)
            for ing in recipe_data["ingredients"]: pdf.multi_cell(190, 10, txt=f"- {ing}")
            pdf.ln(10); pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=14)
            pdf.cell(190, 10, txt="Postup:", ln=True); pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=12)
            pdf.multi_cell(190, 10, txt=recipe_data["instructions"]); pdf.output(pdf_path)
        await hass.async_add_executor_job(generate_pdf)
        data["recipes"][recipe_id] = {
            "id": recipe_id, "title": recipe_data["title"], "ingredients": recipe_data["ingredients"],
            "instructions": recipe_data["instructions"], "url": recipe_data["url"], "image_url": recipe_data.get("image_url", ""),
            "pdf_url": f"/shopping_list_static/recipes/{recipe_id}.pdf", "added_at": dt_util.now().isoformat()
        }
        await store.async_save(data); hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    hass.services.async_register(DOMAIN, "scan_receipt", handle_scan_receipt)
    hass.services.async_register(DOMAIN, "scan_folder", handle_scan_folder)
    hass.services.async_register(DOMAIN, "confirm_receipt", handle_confirm_receipt)
    hass.services.async_register(DOMAIN, "update_inventory", handle_update_inventory)
    hass.services.async_register(DOMAIN, "add_item_by_ean", handle_add_item_by_ean)
    hass.services.async_register(DOMAIN, "add_recipe", handle_add_recipe)
    hass.services.async_register(DOMAIN, "sync_to_keep", handle_sync_to_keep)
    
    hass.http.register_view(ShoppingListPanelView())
    hass.http.register_view(ShoppingListDataView(data))
    hass.http.register_view(ShoppingListUploadView())
    hass.http.register_view(RecipePdfView())

    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        async_register_built_in_panel(
            hass, component_name="custom", sidebar_title="Nákupník", sidebar_icon="mdi:cart-outline", frontend_url_path="shopping-list-ocr",
            config={"_panel_custom": {
                "name": "shopping-list-panel", 
                "module_url": f"/shopping_list_static/panel.js?v={time.time()}"
            }}, require_admin=False,
        )
    except: pass
    return True

async def async_setup(hass: HomeAssistant, config: dict): return True
