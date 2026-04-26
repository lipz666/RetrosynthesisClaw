"""Test script to check different free API options."""

import os
import time
from dataclasses import dataclass
import json
from urllib import error, request

@dataclass
class ModelAPIConfig:
    """Settings for a pluggable model backend."""

    provider: str = "mock"
    api_key: str = ""
    bearer_token: str = ""
    base_url: str = ""
    api_path_template: str = "/v1/chat/completions"
    model_name: str = ""
    auth_scheme: str = "Bearer"
    api_key_header: str = "Authorization"
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "ModelAPIConfig":
        return cls(
            provider=os.getenv("MODEL_PROVIDER", "mock"),
            api_key=os.getenv("MODEL_API_KEY", ""),
            bearer_token=os.getenv("MODEL_BEARER_TOKEN", ""),
            base_url=os.getenv("MODEL_API_BASE_URL", ""),
            api_path_template=os.getenv("MODEL_API_PATH", "/v1/chat/completions"),
            model_name=os.getenv("MODEL_API_NAME", ""),
            auth_scheme=os.getenv("MODEL_AUTH_SCHEME", "Bearer"),
            api_key_header=os.getenv("MODEL_API_KEY_HEADER", "Authorization"),
            timeout_seconds=int(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
        )

    def auth_headers(self) -> dict[str, str]:
        """Build request headers based on the selected auth mode."""

        headers: dict[str, str] = {}
        token = self.bearer_token or self.api_key
        if self.api_key_header.lower() == "authorization" and token:
            value = f"{self.auth_scheme} {token}".strip()
            headers["Authorization"] = value
        elif self.api_key_header.lower() == "x-api-key" and self.api_key:
            headers["x-api-key"] = self.api_key
        elif self.api_key_header.lower() == "x-goog-api-key" and self.api_key:
            headers["x-goog-api-key"] = self.api_key
        elif self.api_key_header.lower() not in {"authorization", "key"} and self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers

    def render_api_path(self) -> str:
        """Render the configured API path template for the current model."""

        path = self.api_path_template.format(model=self.model_name)
        return path if path.startswith("/") else f"/{path}"

class HttpModelClient:
    """OpenAI-compatible chat.completions HTTP implementation."""

    def __init__(self, config: ModelAPIConfig):
        self.config = config

    def generate_retrosynthesis(self, target_smiles: str, context: str = "") -> dict:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.api_key and not self.config.bearer_token:
            raise ValueError("MODEL_API_KEY or MODEL_BEARER_TOKEN is required for HTTP provider")
        if not self.config.model_name:
            raise ValueError("MODEL_API_NAME is required for HTTP provider")

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path()
        system_prompt = (
            "You are a retrosynthesis assistant. Output ONLY valid JSON with keys: "
            "proposal, confidence, target_smiles, context, precursors, reaction_type, notes. "
            "precursors must be a JSON array of immediate precursor SMILES strings. "
            "reaction_type must be a short label. "
            "Do not output markdown. Do not include extra text."
        )
        user_prompt = (
            f"Target SMILES: {target_smiles}\n"
            f"Context: {context}\n"
            "Return exactly one retrosynthetic step."
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "top_p": 1.0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.config.auth_headers(),
        }
        req = request.Request(endpoint, data=data, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                print(f"Response status: {resp.status}")
                print(f"Response content: {raw}")
                return self._parse_response(raw, target_smiles=target_smiles, context=context)
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            print(f"HTTP Error: {exc.code} - {body}")
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            print(f"URL Error: {exc.reason}")
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            print("Timeout Error: request timed out")
            raise RuntimeError("timeout_error: request timed out") from exc

    def _classify_http_error(self, code: int, body: str) -> str:
        if code == 401:
            return f"auth_error_401: {body}"
        if code == 403:
            return f"permission_error_403: {body}"
        if code == 404:
            return f"path_error_404: {body}"
        if code == 429:
            return f"rate_limit_error_429: {body}"
        if 400 <= code < 500:
            return f"client_error_{code}: {body}"
        if code >= 500:
            return f"server_error_{code}: {body}"
        return f"http_error_{code}: {body}"

    def _parse_response(self, raw: str, target_smiles: str, context: str) -> dict:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "proposal": raw.strip() or f"api-backed proposal for {target_smiles}",
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.5,
                "notes": "non-json response from model API",
                "raw_response": raw,
                "precursors": [f"{target_smiles}_precursor_A", f"{target_smiles}_precursor_B"],
                "reaction_type": "unknown",
            }

        if isinstance(decoded, dict):
            choices = decoded.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if isinstance(content, str):
                    try:
                        nested = json.loads(content)
                    except json.JSONDecodeError:
                        nested = None
                    if isinstance(nested, dict):
                        nested.setdefault("target_smiles", target_smiles)
                        nested.setdefault("context", context)
                        nested.setdefault("provider", self.config.provider)
                        nested.setdefault("confidence", 0.6)
                        nested.setdefault("precursors", [f"{target_smiles}_precursor_A", f"{target_smiles}_precursor_B"])
                        nested.setdefault("reaction_type", "unknown")
                        nested["raw_response"] = decoded
                        return nested
                    return {
                        "proposal": content,
                        "target_smiles": target_smiles,
                        "context": context,
                        "provider": self.config.provider,
                        "confidence": 0.6,
                        "notes": "text content response from chat.completions API",
                        "raw_response": decoded,
                        "precursors": [f"{target_smiles}_precursor_A", f"{target_smiles}_precursor_B"],
                        "reaction_type": "unknown",
                    }

        return {
            "proposal": f"api-backed proposal for {target_smiles}",
            "target_smiles": target_smiles,
            "context": context,
            "provider": self.config.provider,
            "confidence": 0.5,
            "notes": "unrecognized model response format",
            "raw_response": decoded,
            "precursors": [f"{target_smiles}_precursor_A", f"{target_smiles}_precursor_B"],
            "reaction_type": "unknown",
        }

def test_api(config_name, config_dict):
    """Test a specific API configuration."""
    print(f"\n{'='*60}")
    print(f"Testing {config_name}")
    print(f"{'='*60}")
    
    # Set environment variables
    for key, value in config_dict.items():
        os.environ[key] = value
    
    # Test API connection
    print("Testing API connection...")
    config = ModelAPIConfig.from_env()
    client = HttpModelClient(config)
    
    try:
        result = client.generate_retrosynthesis("CCO")
        print("\nFinal result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\nAPI test successful!")
        return True
    except Exception as e:
        print(f"\nAPI test failed: {e}")
        return False
    finally:
        # Clean up environment variables
        for key in config_dict.keys():
            if key in os.environ:
                del os.environ[key]
        # Wait to avoid rate limits
        print("Waiting 10 seconds before next test...")
        time.sleep(10)

if __name__ == "__main__":
    # Define API configurations
    api_configs = {
        "Ofox AI (Original)": {
            "MODEL_PROVIDER": "http",
            "MODEL_API_BASE_URL": "https://api.ofox.ai",
            "MODEL_API_PATH": "/v1/chat/completions",
            "MODEL_API_NAME": "z-ai/glm-4.7-flash:free",
            "MODEL_API_KEY": "sk-of-PGxXjqoWuqvnJyQgzZnPwPiYubaIlCkuopgxdGFskfhLdUoTvqLFlajLxEGXWUrF",
            "MODEL_BEARER_TOKEN": "sk-of-PGxXjqoWuqvnJyQgzZnPwPiYubaIlCkuopgxdGFskfhLdUoTvqLFlajLxEGXWUrF",
            "MODEL_API_KEY_HEADER": "Authorization",
            "MODEL_AUTH_SCHEME": "Bearer",
            "MODEL_TIMEOUT_SECONDS": "300"
        },
        "Google Gemini (Free Tier)": {
            "MODEL_PROVIDER": "http",
            "MODEL_API_BASE_URL": "https://generativelanguage.googleapis.com",
            "MODEL_API_PATH": "/v1/models/{model}:generateContent",
            "MODEL_API_NAME": "gemini-1.5-flash",
            "MODEL_API_KEY": "YOUR_GEMINI_API_KEY",  # Replace with your key
            "MODEL_API_KEY_HEADER": "x-goog-api-key",
            "MODEL_TIMEOUT_SECONDS": "300"
        },
        "Anthropic Claude (Free Tier)": {
            "MODEL_PROVIDER": "http",
            "MODEL_API_BASE_URL": "https://api.anthropic.com",
            "MODEL_API_PATH": "/v1/messages",
            "MODEL_API_NAME": "claude-3-haiku-20240307",
            "MODEL_API_KEY": "YOUR_ANTHROPIC_API_KEY",  # Replace with your key
            "MODEL_API_KEY_HEADER": "x-api-key",
            "MODEL_TIMEOUT_SECONDS": "300"
        },
        "Mistral AI (Free Tier)": {
            "MODEL_PROVIDER": "http",
            "MODEL_API_BASE_URL": "https://api.mistral.ai",
            "MODEL_API_PATH": "/v1/chat/completions",
            "MODEL_API_NAME": "mistral-small-latest",
            "MODEL_API_KEY": "YOUR_MISTRAL_API_KEY",  # Replace with your key
            "MODEL_API_KEY_HEADER": "Authorization",
            "MODEL_AUTH_SCHEME": "Bearer",
            "MODEL_TIMEOUT_SECONDS": "300"
        },
        "Cohere (Free Tier)": {
            "MODEL_PROVIDER": "http",
            "MODEL_API_BASE_URL": "https://api.cohere.ai",
            "MODEL_API_PATH": "/v1/chat",
            "MODEL_API_NAME": "command-r-plus",
            "MODEL_API_KEY": "YOUR_COHERE_API_KEY",  # Replace with your key
            "MODEL_API_KEY_HEADER": "Authorization",
            "MODEL_AUTH_SCHEME": "Bearer",
            "MODEL_TIMEOUT_SECONDS": "300"
        }
    }
    
    # Test each API
    for config_name, config_dict in api_configs.items():
        test_api(config_name, config_dict)
    
    print("\n{'='*60}")
    print("All API tests completed!")
    print("{'='*60}")
