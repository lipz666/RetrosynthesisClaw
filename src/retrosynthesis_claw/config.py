"""Configuration helpers for RetrosynthesisClaw."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode


def load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)


# Load environment variables from .env file
load_env_file()


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
    timeout_seconds: int = 300

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

    def query_params(self) -> str:
        """Build optional query parameters for APIs that use `key` in the URL."""

        if self.api_key_header.lower() == "key":
            return "?" + urlencode({"key": self.api_key})
        return ""

    def render_api_path(self) -> str:
        """Render the configured API path template for the current model."""

        path = self.api_path_template.format(model=self.model_name)
        return path if path.startswith("/") else f"/{path}"


@dataclass
class AppConfig:
    """Minimal runtime configuration."""

    name = "RetrosynthesisClaw"
    min_route_steps: int = 5
    max_route_steps: int = 20
    max_branching_factor: int = 5
    model: ModelAPIConfig = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = ModelAPIConfig.from_env()


def load_default_config() -> AppConfig:
    """Load built-in defaults.

    This keeps the scaffold dependency-light. YAML support can be added later.
    """

    return AppConfig()


def ensure_project_dir(path: str | Path) -> Path:
    """Create a project directory if it does not exist."""

    project_path = Path(path)
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path
