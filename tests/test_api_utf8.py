"""Test retrosynthesis via FastAPI with UTF-8 encoding."""

import json
import urllib.request

url = "http://localhost:8000/route"

payload = {
    "target": "BrC1=C2CCCOC2=NC=C1",
    "top_k": 3,
    "debug": True
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing retrosynthesis via FastAPI server")
print("Target: BrC1=C2CCCOC2=NC=C1")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request to FastAPI...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        print("\nSuccess!")
        print("\nResult:")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
