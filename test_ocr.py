import sys
import os
import requests
import json

def test_ocr(api_key):
    print(f"Testing Gemini API with key: {api_key[:5]}...{api_key[-5:]}")
    
    # Test listing models
    print("\n1. Listing available models...")
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=10)
        if r.status_code == 200:
            models = [m['name'] for m in r.json().get('models', [])]
            print(f"   Successfully found {len(models)} models.")
            print(f"   Examples: {models[:5]}")
        else:
            print(f"   Error listing models: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"   Connection failed: {e}")

    # Test a simple prompt
    print("\n2. Testing simple generation (Gemini 1.5 Flash)...")
    payload = {
        "contents": [{"parts": [{"text": "Say 'OCR OK' if you can read this."}]}]
    }
    
    configs = [
        ("v1beta", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-flash"),
        ("v1beta", "gemini-1.5-flash-latest"),
        ("v1beta", "gemini-2.0-flash"),
    ]
    
    for ver, model in configs:
        print(f"   Trying {ver} / {model}...")
        url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                print(f"   SUCCESS! Response: {r.json()['candidates'][0]['content']['parts'][0]['text'].strip()}")
                return
            else:
                print(f"   Failed ({r.status_code}): {r.json().get('error', {}).get('message', 'Unknown error')}")
        except Exception as e:
            print(f"   Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_ocr.py YOUR_GEMINI_API_KEY")
    else:
        test_ocr(sys.argv[1])
