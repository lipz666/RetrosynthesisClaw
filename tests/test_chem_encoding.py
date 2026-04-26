"""Test chemistry prompts with proper encoding."""

import json
import urllib.request
import sys

url = "http://localhost:11434/v1/chat/completions"

payload = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "What does the SMILES CCO represent?"}
    ],
    "stream": False,
    "options": {"num_predict": 150}
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing chemistry prompt with proper encoding")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        result = json.loads(raw)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("Response:")
        print(content)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
