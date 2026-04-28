import asyncio
import aiohttp
import logging
import sys
import os
import re

# Přidat cestu k komponentě
sys.path.append("/home/marcipan/Dokumenty/test/HAos/custom_components/bookcase")

# Mock homeassistant before importing api
import types
mock_ha = types.ModuleType("homeassistant")
mock_ha_helpers = types.ModuleType("homeassistant.helpers")
mock_ha_client = types.ModuleType("homeassistant.helpers.aiohttp_client")

# Persistent session for the test
_session = None

def get_session(hass):
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session

mock_ha_client.async_get_clientsession = get_session
sys.modules["homeassistant"] = mock_ha
sys.modules["homeassistant.helpers"] = mock_ha_helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha_client

# Mock logging to stdout
root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

from api import fetch_book_metadata, fetch_didasko_cz

class MockHass:
    def __init__(self):
        self.data = {}

async def main():
    hass = MockHass()
    isbn = "9788088447634"
    print(f"Hledám metadata pro ISBN: {isbn}...")
    
    try:
        # Testujeme Didasko přímo
        print("\n--- Test Didasko.cz ---")
        session = get_session(hass)
        didasko_res = await fetch_didasko_cz(session, isbn)
        print(f"Didasko výsledek: {didasko_res}")
        
        print("\n--- Celkové vyhledávání ---")
        result = await fetch_book_metadata(hass, isbn)
        
        if result:
            print("\n--- FINÁLNÍ VÝSLEDEK ---")
            print(f"Titul: {result.get('title')}")
            print(f"Autoři: {result.get('authors')}")
            print(f"Nakladatel: {result.get('publishers')}")
            print(f"Zdroj titulu: {result.get('_title_source')}")
            print("------------------------\n")
            
            if result.get('title') == "Učednictví v praxi":
                print("TEST ÚSPĚŠNÝ: Název je správně.")
            else:
                print(f"TEST VAROVÁNÍ: Název je '{result.get('title')}', očekával jsem 'Učednictví v praxi'.")
        else:
            print("TEST SELHAL: Žádná metadata nebyla nalezena.")
            
    except Exception as e:
        print(f"Chyba při testu: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if _session:
            await _session.close()

if __name__ == "__main__":
    asyncio.run(main())
