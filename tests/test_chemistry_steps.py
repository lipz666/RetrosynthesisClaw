"""Test various chemistry prompts to find the limit."""

import json
import urllib.request

url = "http://localhost:11434/v1/chat/completions"

tests = [
    ("Simple math", "What is 2+2?"),
    ("Simple chemistry", "What is the formula of water?"),
    ("IUPAC name", "What is the IUPAC name for CCO?"),
    ("SMILES explanation", "What does the SMILES CCO represent?"),
    ("Simple retrosynthesis", "What is a precursor for ethanol (CCO)?"),
]

headers = {"Content-Type": "application/json"}

for name, prompt in tests:
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"Prompt: {prompt}")
    print("-" * 60)
    
    payload = {
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 100}
    }
    
    data = json.dumps(payload).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"Response: {content[:200]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
