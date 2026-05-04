# Nákupník (Shopping List OCR & Inventory)

Profesionální integrace pro Home Assistant, která kombinuje OCR skenování účtenek, správu domácího skladu a knihovnu receptů s automatickou generací PDF.

## ✨ Hlavní funkce
- **AI OCR (Gemini 1.5 Flash)**: Inteligentní rozpoznávání účtenek s vysokou přesností (pochopení struktury, cen a položek).
- **Manuální fallback**: Možnost ruční opravy nebo doplnění položek přímo v UI, pokud OCR selže.
- **Správa skladu (Grocy-like)**: Sledování zásob, historie cen a automatické doplňování z účtenek.
- **Knihovna receptů**: Stahování receptů z URL, automatická extrakce ingrediencí a generování PDF dokumentů s českou diakritikou.
- **Škálování porcí**: Automatický přepočet ingrediencí podle navoleného počtu porcí před přidáním do nákupu.
- **Moderní UI**: Přehledný panel se záložkami a náhledy produktů/receptů.

## 🚀 Instalace a nastavení
1. Zkopírujte složku `custom_components/shopping_list_ocr` do vašeho adresáře `config` v HA.
2. Restartujte Home Assistant.
3. Přidejte integraci "Nákupník" v nastavení.
4. V **Nastavení -> Zařízení a služby -> Nákupník -> Konfigurovat** vložte své API klíče:
   - **Gemini API Key**: Získáte zdarma na [Google AI Studio](https://aistudio.google.com/app/apikey). (Doporučeno)
   - **OCR.space API Key**: Získáte zdarma na [ocr.space](https://ocr.space/ocrapi). (Záloha)

## 🛠 Služby
- `shopping_list_ocr.scan_receipt`: Skenování jedné účtenky.
- `shopping_list_ocr.scan_folder`: Hromadné skenování složky s obrázky.
- `shopping_list_ocr.add_recipe`: Stažení receptu z URL a vytvoření PDF.
