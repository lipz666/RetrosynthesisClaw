"""Test retrosynthesis for BrC1=C2CCCOC2=NC=C1."""

import json
import urllib.request
import urllib.error

url = "http://localhost:11434/v1/chat/completions"

system_prompt = (
    "You are a retrosynthesis assistant. Output ONLY valid JSON with keys: "
    "proposal, confidence, target_smiles, context, precursors, reaction_type, notes. "
    "precursors must be a JSON array of immediate precursor SMILES strings. "
    "reaction_type must be a short label. "
    "Do not output markdown. Do not include extra text."
)

user_prompt = (
    f"Target SMILES: BrC1=C2CCCOC2=NC=C1\n"
    f"Context: \n"
    "Return exactly one retrosynthetic step."
)

payload = {
    "model": "qwen3:8b",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.2,
    "stream": False,
    "options": {
        "temperature": 0.2,
        "num_predict": 500
    }
}

data = json.dumps(payload).encode("utf-8")
headers = {
    "Content-Type": "application/json"
}

print("Testing retrosynthesis for: BrC1=C2CCCOC2=NC=C1")
print("This molecule is a brominated quinoline/benzofused heterocycle")
print("=" * 60)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request to Ollama...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Response status: {resp.status}")
        
        result = json.loads(raw)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print("\n" + "=" * 60)
        print("Model Response:")
        print("-" * 60)
        print(content)
        print("-" * 60)
        
        try:
            parsed = json.loads(content)
            print("\nParsed JSON Result:")
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print("\nCould not parse response as JSON")
            
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    body = e.read().decode("utf-8")
    print(body)
except Exception as e:
    print(f"Error: {e}")
