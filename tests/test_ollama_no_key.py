"""Test script for Ollama API connection without API key."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

os.environ["MODEL_PROVIDER"] = "http"
os.environ["MODEL_API_BASE_URL"] = "http://localhost:11434"
os.environ["MODEL_API_PATH"] = "/v1/chat/completions"
os.environ["MODEL_API_NAME"] = "qwen3:8b"
os.environ["MODEL_TIMEOUT_SECONDS"] = "300"

import json
from retrosynthesis_claw.config import ModelAPIConfig
from retrosynthesis_claw.model_client import HttpModelClient

print("Testing Ollama API connection WITHOUT API key...")
print("=" * 60)

config = ModelAPIConfig.from_env()
print(f"Base URL: {config.base_url}")
print(f"Model: {config.model_name}")
print(f"API Path: {config.api_path_template}")
print(f"API Key: {config.api_key or 'None'}")
print(f"Bearer Token: {config.bearer_token or 'None'}")

client = HttpModelClient(config)

try:
    result = client.generate_retrosynthesis("CCO")
    print("\n" + "=" * 60)
    print("API test successful! (NO API key required)")
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\nAPI test failed: {e}")
