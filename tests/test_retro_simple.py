"""Test retrosynthesis for a specific molecule."""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

os.environ["MODEL_PROVIDER"] = "http"
os.environ["MODEL_API_BASE_URL"] = "http://localhost:11434"
os.environ["MODEL_API_PATH"] = "/v1/chat/completions"
os.environ["MODEL_API_NAME"] = "qwen3:8b"
os.environ["MODEL_TIMEOUT_SECONDS"] = "300"

from retrosynthesis_claw.config import ModelAPIConfig
from retrosynthesis_claw.model_client import HttpModelClient

target = "BrC1=C2CCCOC2=NC=C1"
print(f"Testing retrosynthesis for: {target}")
print("=" * 60)

config = ModelAPIConfig.from_env()
print(f"Base URL: {config.base_url}")
print(f"Model: {config.model_name}")
print(f"API Path: {config.api_path_template}")

client = HttpModelClient(config)

try:
    print("\nCalling model API...")
    result = client.generate_retrosynthesis(target)
    print("\n" + "=" * 60)
    print("API call successful!")
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\nAPI call failed: {e}")
    import traceback
    traceback.print_exc()
