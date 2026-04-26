"""Test retrosynthesis with simpler prompt."""

import json
import urllib.request

url = "http://localhost:11434/v1/chat/completions"

payload = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "What is the retrosynthesis of BrC1=C2CCCOC2=NC=C1? Give me precursor molecules in SMILES format. Reply with JSON only."}
    ],
    "stream": False,
    "options": {
        "temperature": 0.3,
        "num_predict": 300
    }
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing retrosynthesis with simpler prompt")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("\nModel Response:")
        print("-" * 60)
        print(content[:1000])
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
