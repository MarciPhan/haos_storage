# Nákupník (Shopping List OCR & Inventory)

Profesionální integrace pro Home Assistant, která kombinuje OCR skenování účtenek, správu domácího skladu a knihovnu receptů s automatickou generací PDF.

## ✨ Hlavní funkce
- **Skenování účtenek (OCR)**: Automatické rozpoznání položek a cen z fotografií (podpora pro Tesco, Lidl, Albert a další).
- **Správa skladu (Grocy-like)**: Sledování zásob, historie cen a automatické doplňování z účtenek.
- **Knihovna receptů**: Stahování receptů z URL, automatická extrakce ingrediencí a generování PDF dokumentů s českou diakritikou.
- **Integrace s nákupním seznamem**: Přidávání chybějících ingrediencí do standardního nákupního seznamu HA jedním kliknutím.
- **Moderní UI**: Přehledný panel se záložkami a náhledy produktů/receptů.

## 🚀 Instalace
1. Zkopírujte složku `custom_components/shopping_list_ocr` do vašeho adresáře `config` v HA.
2. Restartujte Home Assistant.
3. Přidejte integraci "Nákupník" v nastavení.

## 🛠 Služby
- `shopping_list_ocr.scan_receipt`: Skenování jedné účtenky.
- `shopping_list_ocr.scan_folder`: Hromadné skenování složky s obrázky.
- `shopping_list_ocr.add_recipe`: Stažení receptu z URL a vytvoření PDF.
