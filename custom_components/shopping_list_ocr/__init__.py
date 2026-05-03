import logging
import os
import uuid
import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.components.http import HomeAssistantView
import homeassistant.util.dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, EVENT_RECEIPTS_UPDATED
from .api import process_receipt_image, fetch_recipe_content

_LOGGER = logging.getLogger(__name__)

class ShoppingListPanelView(HomeAssistantView):
    """View to serve the panel JavaScript file."""
    url = "/shopping_list_static/panel.js"
    name = "api:shopping_list:panel"
    requires_auth = False

    async def get(self, request):
        file_path = os.path.join(os.path.dirname(__file__), "www", "panel.js")
        if not os.path.exists(file_path):
            from aiohttp import web
            return web.Response(status=404)
        from aiohttp import web
        return web.FileResponse(file_path)

class ShoppingListDataView(HomeAssistantView):
    """View to serve the current data."""
    url = "/api/shopping_list/data"
    name = "api:shopping_list:data"
    requires_auth = True

    def __init__(self, data):
        self._data = data

    async def get(self, request):
        from aiohttp import web
        return web.json_response(self._data)

class RecipePdfView(HomeAssistantView):
    """View to serve generated recipe PDFs."""
    url = "/shopping_list_static/recipes/{recipe_id}.pdf"
    name = "api:shopping_list:recipe_pdf"
    requires_auth = False

    async def get(self, request, recipe_id):
        file_path = os.path.join(os.path.dirname(__file__), "www", "recipes", f"{recipe_id}.pdf")
        if not os.path.exists(file_path):
            from aiohttp import web
            return web.Response(status=404)
        from aiohttp import web
        return web.FileResponse(file_path)

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Shopping List OCR from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {"inventory": {}, "pending_receipts": {}, "recipes": {}}
    if "recipes" not in data:
        data["recipes"] = {}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    async def handle_scan_receipt(call: ServiceCall):
        """Service to scan a single receipt image."""
        image_path = call.data.get("image_path")
        if not image_path or not os.path.exists(image_path):
            _LOGGER.error("Image path %s does not exist", image_path)
            return

        items = await process_receipt_image(hass, image_path)
        if items:
            receipt_id = str(uuid.uuid4())
            data["pending_receipts"][receipt_id] = {
                "id": receipt_id,
                "date": dt_util.now().isoformat(),
                "items": items,
                "image_path": image_path
            }
            await store.async_save(data)
            hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)
            _LOGGER.info("Successfully scanned receipt with %d items", len(items))
        else:
            _LOGGER.warning("No items found on receipt %s", image_path)

    async def handle_scan_folder(call: ServiceCall):
        """Service to scan all images in a folder."""
        folder_path = call.data.get("folder_path")
        if not folder_path or not os.path.isdir(folder_path):
            _LOGGER.error("Folder path %s does not exist", folder_path)
            return

        extensions = ('.jpg', '.jpeg', '.png', '.webp')
        found_new = False
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(extensions):
                image_path = os.path.join(folder_path, filename)
                
                # Check if already scanned
                already_scanned = any(r.get("image_path") == image_path for r in data["pending_receipts"].values())
                if already_scanned: continue

                items = await process_receipt_image(hass, image_path)
                if items:
                    receipt_id = str(uuid.uuid4())
                    data["pending_receipts"][receipt_id] = {
                        "id": receipt_id,
                        "date": dt_util.now().isoformat(),
                        "items": items,
                        "image_path": image_path
                    }
                    found_new = True
        
        if found_new:
            await store.async_save(data)
            hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)
        _LOGGER.info("Finished scanning folder: %s", folder_path)

    async def handle_confirm_receipt(call: ServiceCall):
        """Confirm items from a pending receipt and add them to inventory."""
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
                        "name": name,
                        "quantity": item["quantity"],
                        "last_price": item["price"],
                        "unit": item.get("unit", "ks"),
                        "min_quantity": 0,
                        "expiry_days": 0
                    }
            await store.async_save(data)
            hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_update_inventory(call: ServiceCall):
        """Manually update inventory items."""
        item_name = call.data.get("name")
        if not item_name: return
        
        action = call.data.get("action", "update")
        if action == "delete":
            data["inventory"].pop(item_name, None)
        else:
            data["inventory"][item_name] = {
                "name": item_name,
                "quantity": call.data.get("quantity", 0),
                "last_price": call.data.get("last_price", 0),
                "unit": call.data.get("unit", "ks"),
                "min_quantity": call.data.get("min_quantity", 0),
                "expiry_days": call.data.get("expiry_days", 0)
            }
        await store.async_save(data)
        hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)

    async def handle_add_recipe(call: ServiceCall):
        """Service to fetch a recipe from URL and generate PDF."""
        url = call.data.get("url")
        if not url: return

        recipe_data = await fetch_recipe_content(hass, url)
        if not recipe_data:
            _LOGGER.error("Could not fetch recipe from %s", url)
            return

        recipe_id = str(uuid.uuid4())
        pdf_filename = f"{recipe_id}.pdf"
        pdf_path = os.path.join(os.path.dirname(__file__), "www", "recipes", pdf_filename)

        # Generate PDF
        def generate_pdf():
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            
            # Try to load a font that supports Czech characters
            font_path = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
            font_loaded = False
            if os.path.exists(font_path):
                try:
                    pdf.add_font("DejaVu", "", font_path)
                    pdf.set_font("DejaVu", size=16)
                    font_loaded = True
                except:
                    pass
            
            if not font_loaded:
                pdf.set_font("Helvetica", style="B", size=16)
            
            # Title
            pdf.cell(190, 10, txt=recipe_data["title"], ln=True, align='C')
            pdf.ln(10)
            
            # Ingredients header
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=14)
            pdf.cell(190, 10, txt="Ingredience:", ln=True)
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=12)
            for ing in recipe_data["ingredients"]:
                pdf.multi_cell(190, 10, txt=f"- {ing}")
            
            pdf.ln(10)
            
            # Instructions header
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=14)
            pdf.cell(190, 10, txt="Postup:", ln=True)
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=12)
            pdf.multi_cell(190, 10, txt=recipe_data["instructions"])
            
            pdf.ln(10)
            pdf.set_font("Helvetica" if not font_loaded else "DejaVu", size=10)
            pdf.cell(190, 10, txt=f"Zdroj: {recipe_data['url']}", ln=True)
            
            pdf.output(pdf_path)

        await hass.async_add_executor_job(generate_pdf)

        # Save to data
        data["recipes"][recipe_id] = {
            "id": recipe_id,
            "title": recipe_data["title"],
            "ingredients": recipe_data["ingredients"],
            "instructions": recipe_data["instructions"],
            "url": recipe_data["url"],
            "pdf_url": f"/shopping_list_static/recipes/{pdf_filename}",
            "added_at": dt_util.now().isoformat()
        }
        
        await store.async_save(data)
        hass.bus.async_fire(EVENT_RECEIPTS_UPDATED)
        _LOGGER.info("Successfully added recipe: %s", recipe_data["title"])

    # Registrace služeb
    hass.services.async_register(DOMAIN, "scan_receipt", handle_scan_receipt)
    hass.services.async_register(DOMAIN, "scan_folder", handle_scan_folder)
    hass.services.async_register(DOMAIN, "confirm_receipt", handle_confirm_receipt)
    hass.services.async_register(DOMAIN, "update_inventory", handle_update_inventory)
    hass.services.async_register(DOMAIN, "add_recipe", handle_add_recipe)

    # Registrace HTTP view
    hass.http.register_view(ShoppingListPanelView())
    hass.http.register_view(ShoppingListDataView(data))
    hass.http.register_view(RecipePdfView())

    # Registrace panelu
    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Nákupník",
            sidebar_icon="mdi:cart-outline",
            frontend_url_path="shopping-list-ocr",
            config={"_panel_custom": {
                "name": "shopping-list-panel",
                "module_url": "/shopping_list_static/panel.js"
            }},
            require_admin=False,
        )
    except Exception as e:
        _LOGGER.error("Error registering panel: %s", e)

    return True

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component from configuration.yaml (optional)."""
    return True
