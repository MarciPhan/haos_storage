import re
text = """Tady je výsledek:
```json
{
  "store": "Tesco",
  "items": [{"name": "A", "price": 10}]
}
```
Užijte si to!
"""
match = re.search(r'\{.*\}', text, re.DOTALL)
if match:
    print(match.group(0))
