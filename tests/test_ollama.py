"""Test Ollama API response format."""
import os
import json
import urllib.request
import urllib.error

# Load env
from pathlib import Path
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Get config
base_url = os.getenv("MODEL_API_BASE_URL", "")
model_name = os.getenv("MODEL_API_NAME", "")
api_key = os.getenv("MODEL_API_KEY", "") or os.getenv("MODEL_BEARER_TOKEN", "")

print(f"Base URL: {base_url}")
print(f"Model: {model_name}")
print(f"Has API Key: {bool(api_key)}")

if not base_url or not model_name:
    print("ERROR: MODEL_API_BASE_URL and MODEL_API_NAME must be set")
    exit(1)

# Test request
endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
payload = {
    "model": model_name,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant. Reply with JSON only."},
        {"role": "user", "content": "Say hello in JSON with fields: message and status"}
    ],
    "temperature": 0.1,
    "max_tokens": 500,
}

data = json.dumps(payload).encode("utf-8")
headers = {
    "Content-Type": "application/json",
}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        print("\n=== Raw Response ===")
        print(raw[:2000])
        print("\n=== Parsed Response ===")
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2, ensure_ascii=False)[:2000])
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    body = e.read().decode("utf-8")
    print(body[:2000])
except Exception as e:
    print(f"Error: {e}")
