"""FastAPI application for RetrosynthesisClaw."""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path
import base64
import json
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .chemistry import export_molecule, normalize_molecule
from .config import load_default_config
from .model_client import HttpModelClient, build_model_client
from .orchestrator import RetrosynthesisOrchestrator
from .types import FragmentExecutionTask
from .yield_predictor.yield_predictor import get_yield_predictor, predict_yield, predict_yield_batch

BASE_DIR = Path(__file__).resolve().parents[2]
API_CONFIG_PATH = BASE_DIR / "configs" / "api_config.json"
FRONTEND_DIR = BASE_DIR / "frontend"
PUBLIC_DIR = BASE_DIR / "public"
STANDALONE_DIR = PUBLIC_DIR / "standalone"

rdkit_available = False
try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    rdkit_available = True
except ImportError:
    pass

app = FastAPI(title="RetrosynthesisClaw", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"], expose_headers=["*"], max_age=86400)
if FRONTEND_DIR.exists(): app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
if PUBLIC_DIR.exists(): app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR), html=False), name="public")
if STANDALONE_DIR.exists(): app.mount("/standalone", StaticFiles(directory=str(STANDALONE_DIR), html=True), name="standalone")


class RouteRequest(BaseModel):
    target: str = Field(..., description="Target molecule in SMILES or name form")
    top_k: int = Field(3, ge=1, le=10, description="Number of candidate routes to return")
    debug: bool = Field(False, description="Include debug details in the response")


class RouteResponse(BaseModel):
    result: dict
    retrosynthesis_plan: dict | None = None
    route_count: int = 0
    selected_route: dict | None = None
    execution_fragments: list[dict] = Field(default_factory=list)
    execution_status: str = "pending"
    synthesis_route: dict | None = None


class MoleculeTextRequest(BaseModel):
    text: str = Field(..., description="SMILES or common chemical name")


class FragmentExecutionRequest(BaseModel):
    task: FragmentExecutionTask


class FragmentExecutionBatchRequest(BaseModel):
    route_id: str
    target_smiles: str
    fragments: list[dict]
    execution_strategy: str = "sequential_execution"
    instructions: str = ""


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _default_api_config() -> dict:
    return {"name": "RetrosynthesisClaw API", "url": "http://127.0.0.1:8000/route", "method": "POST", "auth": {"type": "none"}, "headers": [{"key": "Content-Type", "value": "application/json"}, {"key": "Accept", "value": "application/json"}], "params": {"query": [], "body": {"format": "json", "content": json.dumps({"target": "CCO", "top_k": 3, "debug": False}, ensure_ascii=False, indent=2)}}, "response": {"expectedStatusCode": 200, "format": "json"}}


def _load_api_config_file() -> dict:
    default = _default_api_config()
    if not API_CONFIG_PATH.exists():
        API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        API_CONFIG_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    try:
        return _normalize_api_config(json.loads(API_CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        return default


def _normalize_api_config(config: dict | None) -> dict:
    default = _default_api_config()
    if not isinstance(config, dict): return default
    normalized = {**default, **config}
    normalized["auth"] = {**default["auth"], **(config.get("auth") or {})}
    normalized["headers"] = config.get("headers") or default["headers"]
    params = config.get("params") or {}
    normalized["params"] = {"query": params.get("query") or default["params"]["query"], "body": {**default["params"]["body"], **(params.get("body") or {})}}
    normalized["response"] = {**default["response"], **(config.get("response") or {})}
    normalized["response"]["expectedStatusCode"] = int(normalized["response"].get("expectedStatusCode", 200))
    return normalized


@app.get("/config")
def config() -> dict:
    cfg = load_default_config()
    return {"name": cfg.name, "min_route_steps": cfg.min_route_steps, "max_route_steps": cfg.max_route_steps, "max_branching_factor": cfg.max_branching_factor, "model_provider": cfg.model.provider, "model_base_url": cfg.model.base_url, "model_api_path_template": cfg.model.api_path_template, "model_name": cfg.model.model_name, "model_auth_scheme": cfg.model.auth_scheme, "model_api_key_header": cfg.model.api_key_header, "has_bearer_token": bool(cfg.model.bearer_token or cfg.model.api_key), "api_config": _load_api_config_file()}


@app.get("/config/api")
def get_api_config() -> dict:
    return _load_api_config_file()


@app.post("/config/api")
def set_api_config(config_payload: dict) -> dict:
    normalized = _normalize_api_config(config_payload)
    API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    API_CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


@app.get("/api/config")
def get_api_config_legacy() -> dict:
    return _load_api_config_file()


@app.post("/api/config")
def set_api_config_legacy(config_payload: dict) -> dict:
    return set_api_config(config_payload)


@app.get("/model-test")
def model_test() -> dict:
    cfg = load_default_config()
    client = build_model_client(cfg.model)
    if not isinstance(client, HttpModelClient): return {"ok": False, "message": "MODEL_PROVIDER is not http/api/remote"}
    try:
        return {"ok": True, "result": client.generate_forward_synthesis("CCO", context="model-test")}
    except Exception as exc:
        message = str(exc)
        error_type = "unknown_error"
        if message.startswith("auth_error_401"): error_type = "auth_error"
        elif message.startswith("permission_error_403"): error_type = "permission_error"
        elif message.startswith("path_error_404"): error_type = "path_error"
        elif message.startswith("rate_limit_error_429"): error_type = "rate_limit_error"
        elif message.startswith("server_error_"): error_type = "server_error"
        elif message.startswith("connection_error:"): error_type = "connection_error"
        elif message.startswith("timeout_error:"): error_type = "timeout_error"
        return {"ok": False, "error_type": error_type, "error": message}


@app.post("/molecule/normalize")
def molecule_normalize(request: MoleculeTextRequest) -> dict:
    return normalize_molecule(request.text).__dict__


@app.post("/molecule/export")
def molecule_export(request: MoleculeTextRequest) -> dict:
    return export_molecule(request.text).__dict__


@app.post("/molecule/iupac")
def molecule_iupac(request: MoleculeTextRequest) -> dict:
    result = export_molecule(request.text)
    return {"input_text": result.input_text, "iupac_name": result.iupac_name, "valid": result.valid, "notes": result.notes}


@app.options("/route")
def route_options():
    return {}


@app.post("/route", response_model=RouteResponse)
def route(request: RouteRequest) -> RouteResponse:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    plan = orchestrator.run(request.target, top_k=request.top_k)
    result = plan.to_dict()
    if request.debug:
        result["debug"] = {"config": config()}
    return RouteResponse(
        result=result,
        retrosynthesis_plan=result,
        synthesis_route=result,
        route_count=result.get("route_count", len(result.get("routes", []))),
        selected_route=result.get("selected_route"),
        execution_fragments=result.get("execution_fragments", []),
        execution_status=result.get("execution_status", "pending"),
    )


@app.post("/route/stream")
def route_stream(request: RouteRequest) -> StreamingResponse:
    orchestrator = RetrosynthesisOrchestrator.create_default()

    def serialize(value):
        if hasattr(value, "to_dict"): return value.to_dict()
        if hasattr(value, "model_dump"): return value.model_dump()
        if hasattr(value, "__dict__"): return asdict(value) if hasattr(value, "__dataclass_fields__") else value.__dict__
        if isinstance(value, list): return [serialize(item) for item in value]
        if isinstance(value, dict): return {key: serialize(item) for key, item in value.items()}
        return value

    def event_stream():
        for event in orchestrator.iterate(request.target, top_k=request.top_k):
            yield f"data: {json.dumps(serialize(event), ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/chain/stream")
def chain_stream(request: RouteRequest) -> StreamingResponse:
    return route_stream(request)


@app.post("/route/debug")
def route_debug(request: RouteRequest) -> dict:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    plan = orchestrator.run(request.target, top_k=request.top_k)
    result = plan.to_dict()
    return {"request": request.model_dump(), "config": config(), "result": result, "raw_model_responses": [step.get("metadata", {}).get("model_response") for route in result.get("routes", []) for step in route.get("steps", []) if step.get("metadata", {}).get("model_response") is not None]}


@app.post("/fragment/execute")
def execute_fragment(request: FragmentExecutionRequest) -> dict:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    result = orchestrator.executor.run(request.task)
    return result.to_dict()


@app.post("/fragment/execute/route")
def execute_fragment_route(request: RouteRequest) -> dict:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    plan = orchestrator.run(request.target, top_k=request.top_k)
    plan_dict = plan.to_dict()
    return {"plan": plan_dict, "route_count": plan_dict.get("route_count", 0), "execution_fragments": plan_dict.get("execution_fragments", []), "execution_status": plan_dict.get("execution_status", "pending")}


@app.post("/fragment/execute/batch")
def execute_fragment_batch(request: FragmentExecutionBatchRequest) -> dict:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    tasks = []
    for idx, fragment in enumerate(request.fragments, start=1):
        task = FragmentExecutionTask(task_id=f"{request.route_id}:{fragment.get('fragment_id', f'fragment-{idx}')}", route_id=request.route_id, fragment_id=fragment.get('fragment_id', f'fragment-{idx}'), fragment_smiles=fragment.get('fragment_smiles', ''), target_smiles=request.target_smiles, execution_strategy=fragment.get('strategy', request.execution_strategy), instructions=fragment.get('instructions', request.instructions), order_index=int(fragment.get('order_index', idx)), dependencies=list(fragment.get('dependencies', [])) if isinstance(fragment.get('dependencies', []), list) else [], metadata={"fragment": fragment})
        tasks.append(task)
    results = []
    for task in tasks:
        results.append(orchestrator.executor.run(task).to_dict())
    execution_status = "completed" if results and all(item.get("status") == "completed" for item in results) else "partial" if results else "pending"
    return {"route_id": request.route_id, "target_smiles": request.target_smiles, "task_count": len(tasks), "execution_status": execution_status, "tasks": [task.to_dict() for task in tasks], "results": results}


@app.get("/molecule/image")
def molecule_image(smiles: str, width: int = 200, height: int = 200) -> Response:
    if not smiles: return Response(content="SMILES is required", status_code=400, media_type="text/plain")
    if rdkit_available:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None: return Response(content="Invalid SMILES", status_code=400, media_type="text/plain")
            img = Draw.MolToImage(mol, size=(width, height))
            buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            return Response(content=buf.getvalue(), media_type="image/png")
        except Exception:
            pass
    try:
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(f"""
from rdkit import Chem
from rdkit.Chem import Draw
from io import BytesIO
import base64
import sys
smiles = sys.argv[1]
width = int(sys.argv[2])
height = int(sys.argv[3])
mol = Chem.MolFromSmiles(smiles)
if mol is None:
    print('Invalid SMILES')
    sys.exit(1)
img = Draw.MolToImage(mol, size=(width, height))
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)
print(base64.b64encode(buf.getvalue()).decode('utf-8'))
""")
            script_path = f.name
        cmd = f"conda activate chem_interpret && python {script_path} {smiles} {width} {height}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        os.unlink(script_path)
        if result.returncode != 0: return Response(content=f"Error generating image in conda environment: {result.stderr}", status_code=500, media_type="text/plain")
        img_base64 = result.stdout.strip()
        if not img_base64 or img_base64 == "Invalid SMILES": return Response(content="Invalid SMILES", status_code=400, media_type="text/plain")
        return Response(content=base64.b64decode(img_base64), media_type="image/png")
    except Exception as e:
        try:
            import requests
            pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{smiles}/PNG"
            response = requests.get(pubchem_url, timeout=10)
            if response.status_code == 200:
                return Response(content=response.content, media_type="image/png")
        except Exception:
            pass
        return Response(content=f"Error generating image: {str(e)}", status_code=500, media_type="text/plain")


class YieldPredictRequest(BaseModel):
    reactant_smiles: str = Field(..., description="反应物SMILES (单个分子或两个分子用点分隔)")
    product_smiles: str = Field(..., description="产物SMILES")


class YieldPredictResponse(BaseModel):
    reactant_smiles: str
    product_smiles: str
    predicted_yield: float
    rf_baseline_pred: float
    status: str


class YieldPredictBatchRequest(BaseModel):
    samples: list[dict[str, str]] = Field(..., description="样本列表，每个样本包含 reactant_smiles 和 product_smiles")


class YieldPredictBatchResponse(BaseModel):
    n_samples: int
    predictions: list[dict]


@app.post("/yield/predict", response_model=YieldPredictResponse)
async def yield_predict(request: YieldPredictRequest) -> YieldPredictResponse:
    try:
        result = predict_yield(request.reactant_smiles, request.product_smiles)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return YieldPredictResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@app.post("/yield/predict_batch", response_model=YieldPredictBatchResponse)
async def yield_predict_batch(request: YieldPredictBatchRequest) -> YieldPredictBatchResponse:
    try:
        predictions = predict_yield_batch(request.samples)
        return YieldPredictBatchResponse(n_samples=len(predictions), predictions=predictions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量预测失败: {str(e)}")


@app.get("/yield/health")
async def yield_health() -> dict:
    try:
        predictor = get_yield_predictor(); predictor.load_predictor(); return {"status": "ok", "message": "产率预测模型加载成功"}
    except Exception as e:
        return {"status": "error", "message": f"模型加载失败: {str(e)}"}
