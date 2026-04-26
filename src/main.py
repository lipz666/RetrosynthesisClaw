from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
CONFIG_DIR = BASE_DIR / "configs"
API_CONFIG_PATH = CONFIG_DIR / "api_config.json"
DEFAULT_FRONTEND_ORIGIN = "http://127.0.0.1:5500"


class APIConfigPayload(BaseModel):
    name: str = "RetrosynthesisClaw API"
    url: str = "http://127.0.0.1:8000/route"
    method: str = "POST"
    auth: dict[str, Any] = Field(default_factory=lambda: {"type": "none"})
    headers: list[dict[str, str]] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=lambda: {"query": [], "body": {"format": "json", "content": ""}})
    response: dict[str, Any] = Field(default_factory=lambda: {"expectedStatusCode": 200, "format": "json"})


app = FastAPI(title="RetrosynthesisClaw API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _default_api_config() -> dict[str, Any]:
    return {
        "name": "RetrosynthesisClaw API",
        "url": "http://127.0.0.1:8000/route",
        "method": "POST",
        "auth": {"type": "none"},
        "headers": [
            {"key": "Content-Type", "value": "application/json"},
            {"key": "Accept", "value": "application/json"},
        ],
        "params": {
            "query": [],
            "body": {
                "format": "json",
                "content": json.dumps({"target": "CCO", "top_k": 3, "debug": False}, ensure_ascii=False, indent=2),
            },
        },
        "response": {"expectedStatusCode": 200, "format": "json"},
    }


def load_api_config() -> dict[str, Any]:
    _ensure_config_dir()
    if not API_CONFIG_PATH.exists():
        save_api_config(_default_api_config())
    try:
        return json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"API 配置文件损坏: {exc}") from exc


def save_api_config(config: dict[str, Any]) -> None:
    _ensure_config_dir()
    API_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/")
def root() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return FileResponse(BASE_DIR / "README.md")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config/api")
def get_api_config() -> dict[str, Any]:
    return load_api_config()


@app.post("/config/api")
def update_api_config(payload: APIConfigPayload) -> dict[str, Any]:
    config = payload.model_dump()
    save_api_config(config)
    return {"ok": True, "config": config}


@app.get("/api/config")
def legacy_get_api_config() -> dict[str, Any]:
    return load_api_config()


@app.post("/api/config")
def legacy_update_api_config(payload: APIConfigPayload) -> dict[str, Any]:
    config = payload.model_dump()
    save_api_config(config)
    return {"ok": True, "config": config}
