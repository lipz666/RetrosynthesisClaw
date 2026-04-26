"""Minimal test for Ollama."""

import json
import urllib.request
import urllib.error

url = "http://localhost:11434/v1/chat/completions"

payload = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "Hi"}
    ],
    "stream": False
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Minimal test - just saying 'Hi'")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        print(f"Response: {raw[:200]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
