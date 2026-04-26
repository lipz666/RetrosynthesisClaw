"""Test with medium complexity prompt."""

import json
import urllib.request

url = "http://localhost:11434/v1/chat/completions"

payload = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "What is 2+2?"}
    ],
    "stream": False
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Test 1: Simple math")
try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Status: {resp.status}")
        result = json.loads(resp.read().decode("utf-8"))
        print(f"Response: {result['choices'][0]['message']['content'][:100]}")
except Exception as e:
    print(f"Error: {e}")

# Second test - slightly more complex
payload2 = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "What is the IUPAC name for CCO?"}
    ],
    "stream": False
}

data2 = json.dumps(payload2).encode("utf-8")

print("\nTest 2: Chemistry question")
try:
    req2 = urllib.request.Request(url, data=data2, headers=headers, method="POST")
    with urllib.request.urlopen(req2, timeout=60) as resp:
        print(f"Status: {resp.status}")
        result2 = json.loads(resp.read().decode("utf-8"))
        print(f"Response: {result2['choices'][0]['message']['content'][:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\nTest 3: Retrosynthesis request")
payload3 = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "user", "content": "Give me one precursor for ethanol (CCO)"}
    ],
    "stream": False,
    "options": {"num_predict": 100}
}

data3 = json.dumps(payload3).encode("utf-8")

try:
    req3 = urllib.request.Request(url, data=data3, headers=headers, method="POST")
    with urllib.request.urlopen(req3, timeout=60) as resp:
        print(f"Status: {resp.status}")
        result3 = json.loads(resp.read().decode("utf-8"))
        print(f"Response: {result3['choices'][0]['message']['content'][:200]}")
except Exception as e:
    print(f"Error: {e}")
