"""Test direct Ollama chat API for target molecule."""

import json
import urllib.request

url = "http://localhost:11434/v1/chat/completions"

target_smiles = "BrC1=C2CCCOC2=NC=C1"

payload = {
    "model": "qwen3:8b",
    "messages": [
        {
            "role": "system",
            "content": "You are a retrosynthesis assistant. Output ONLY valid JSON with keys: proposal, confidence, target_smiles, context, precursors, reaction_type, notes. precursors must be a JSON array of immediate precursor SMILES strings. reaction_type must be a short label. Do not output markdown. Do not include extra text."
        },
        {
            "role": "user",
            "content": f"Target SMILES: {target_smiles}\n\nReturn exactly one retrosynthetic step."
        }
    ],
    "temperature": 0.2,
    "top_p": 1.0,
    "stream": False,
    "response_format": {"type": "json_object"}
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing direct Ollama chat API for target molecule:")
print(f"Target: {target_smiles}")
print("=" * 70)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request to Ollama chat API...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        
        print("\nSuccess!")
        print("Raw Ollama response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
                try:
                    json_response = json.loads(content)
                    print("\nParsed JSON response:")
                    print(json.dumps(json_response, indent=2, ensure_ascii=False))
                    print("\n✅ Direct Ollama chat API call successful!")
                except json.JSONDecodeError:
                    print("\n⚠️  Response is not valid JSON:")
                    print(content)
                    print("\n❌ Failed to parse JSON response")
            else:
                print("\n❌ No message content in response")
        else:
            print("\n❌ No choices in response")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
