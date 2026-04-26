"""Simple test for Ollama API connection."""

import json
from urllib import request, error

def test_ollama_api():
    print("Testing Ollama API connection...")
    print("=" * 60)
    
    url = "http://localhost:11434/v1/chat/completions"
    
    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "system",
                "content": "You are a retrosynthesis assistant. Output ONLY valid JSON with keys: proposal, confidence, target_smiles, context, precursors, reaction_type, notes. precursors must be a JSON array of immediate precursor SMILES strings. reaction_type must be a short label. Do not output markdown. Do not include extra text."
            },
            {
                "role": "user",
                "content": "Target SMILES: CCO\nContext: \nReturn exactly one retrosynthetic step."
            }
        ],
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"}
    }
    
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        req = request.Request(url, data=data, headers=headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            print(f"Response status: {resp.status}")
            
            # Parse response
            result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content")
            
            print("\n" + "=" * 60)
            print("API test successful! (NO API key required)")
            print("\nModel response:")
            print(content)
            
            return True
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        print(f"HTTP Error: {exc.code} - {body}")
        return False
    except error.URLError as exc:
        print(f"URL Error: {exc.reason}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_ollama_api()
