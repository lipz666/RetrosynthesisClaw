"""Test direct Ollama API call for target molecule."""

import json
import urllib.request

url = "http://localhost:11434/api/generate"

target_smiles = "BrC1=C2CCCOC2=NC=C1"

payload = {
    "model": "qwen3:8b",
    "prompt": f"Target SMILES: {target_smiles}\n\nReturn exactly one retrosynthetic step. Output ONLY valid JSON with keys: proposal, confidence, target_smiles, context, precursors, reaction_type, notes. precursors must be a JSON array of immediate precursor SMILES strings. reaction_type must be a short label. Do not output markdown. Do not include extra text.",
    "stream": False,
    "options": {
        "temperature": 0.2,
        "num_predict": 300
    }
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print("Testing direct Ollama API call for target molecule:")
print(f"Target: {target_smiles}")
print("=" * 70)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request to Ollama...")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        
        print("\nSuccess!")
        print("Raw Ollama response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if "response" in result:
            response_text = result["response"]
            try:
                json_response = json.loads(response_text)
                print("\nParsed JSON response:")
                print(json.dumps(json_response, indent=2, ensure_ascii=False))
                print("\n✅ Direct Ollama API call successful!")
            except json.JSONDecodeError:
                print("\n⚠️  Response is not valid JSON:")
                print(response_text)
                print("\n❌ Failed to parse JSON response")
        else:
            print("\n❌ No response field in Ollama result")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
