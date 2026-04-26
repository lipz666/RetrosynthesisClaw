"""Test route endpoint with simple molecule."""

import json
import urllib.request

url = "http://localhost:8000/route"

payload = {
    "target": "CCO",
    "top_k": 1,
    "debug": False
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing /route endpoint with simple molecule: CCO")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        print("\nSuccess!")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1500])
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
