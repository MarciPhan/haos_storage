import json
import re
import asyncio

# Mock Gemini response based on user's prompt
text = """```json
{
  "store": "Tesco Stores ČR a.s.",
  "date": "2026-05-03T15:17:28",
  "total": "182,97",
  "items": [
    {"name": "SPAK BARBEC. OM. 320ml", "price": "89,90", "quantity": 1, "expiry_days": 180},
    {"name": "ODK SLOV. KRAJ. 400g", "price": "37,90", "quantity": 1, "expiry_days": 3},
    {"name": "TS EDAM PLATKY 100g", "price": "75,60", "quantity": 4, "expiry_days": 14},
    {"name": "BOH TRV. MLEK. 1.5% 1L", "price": "8,90", "quantity": 1, "expiry_days": 30}
  ]
}
```"""

def parse_num(v, is_int=False):
    if v is None: return 0 if not is_int else 1
    v_str = str(v).replace(',', '.').strip()
    v_str = re.sub(r'[^\d.-]', '', v_str)
    try:
        return int(float(v_str)) if is_int else float(v_str)
    except ValueError:
        return 0 if not is_int else 1

text = text.strip()
if text.startswith("```json"): text = text[7:]
elif text.startswith("```"): text = text[3:]
if text.endswith("```"): text = text[:-3]
text = text.strip()

data = json.loads(text)
data["total"] = parse_num(data.get("total"))
items = data.get("items", [])
for item in items:
    item["price"] = parse_num(item.get("price"), is_int=False)
    item["quantity"] = parse_num(item.get("quantity", 1), is_int=True)
    exp = item.get("expiry_days")
    item["expiry_days"] = int(exp) if exp is not None else None
data["items"] = items

print(json.dumps(data, indent=2, ensure_ascii=False))
