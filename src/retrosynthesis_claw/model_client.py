"""Pluggable model client interface."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from urllib import error, request

from .config import ModelAPIConfig


class ModelClient(Protocol):
    """Interface for any synthesis-capable model backend."""

    def generate_forward_synthesis(
        self,
        target_smiles: str,
        context: str = "",
        temperature: float = 0.1,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """Return a structured model-produced proposal."""

    def generate_synthesis_strategy(
        self,
        target_smiles: str,
        context: str = "",
        temperature: float = 0.1,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """Return a comprehensive synthesis strategy."""


@dataclass
class MockModelClient:
    """Fallback implementation used for scaffolding and tests."""

    config: ModelAPIConfig

    def generate_synthesis_strategy(self, target_smiles: str, context: str = "", temperature: float = 0.1, top_p: float = 0.9) -> Dict[str, Any]:
        return {
            "strategy": f"Mock synthesis strategy for {target_smiles}. This is a mock implementation that would normally provide a comprehensive synthesis plan with estimated steps and rationale.",
            "target_smiles": target_smiles,
            "context": context,
            "provider": self.config.provider,
            "confidence": 0.5,
            "notes": "mock synthesis strategy",
        }

    def generate_forward_synthesis(self, target_smiles: str, context: str = "", temperature: float = 0.1, top_p: float = 0.9) -> Dict[str, Any]:
        return {
            "proposal": f"mock synthesis proposal for {target_smiles}",
            "target_smiles": target_smiles,
            "context": context,
            "provider": self.config.provider,
            "confidence": 0.5,
            "precursors": [f"{target_smiles}_precursor_A", f"{target_smiles}_precursor_B"],
            "reaction_type": "mock_disconnection",
            "notes": "mock single-step proposal",
        }


@dataclass
class HttpModelClient:
    """Ofox OpenAI-compatible chat.completions HTTP implementation."""

    config: ModelAPIConfig

    def generate_synthesis_strategy(self, target_smiles: str, context: str = "", temperature: float = 0.1, top_p: float = 0.9) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            raise ValueError("MODEL_API_NAME is required for HTTP provider")

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        system_prompt = (
            "You are a senior organic synthesis strategist. "
            "Your task is to analyze a target molecule and create a comprehensive synthesis strategy. "
            "Focus on providing a clear, concise plan that outlines the overall approach.\n\n"
            "Requirements:\n"
            "1. Analyze the target molecule structure and identify key functional groups and structural features\n"
            "2. Propose a strategic synthesis plan with estimated number of steps\n"
            "3. Explain the rationale behind each key step\n"
            "4. Justify why this approach is optimal\n"
            "5. Keep the explanation around 200 words\n"
            "6. Output only the synthesis strategy in natural English\n"
            "7. Do not include any JSON or structured format\n"
            "8. Focus on strategic planning, not detailed reaction conditions\n"
        )
        user_prompt = (
            f"Target SMILES: {target_smiles}\n"
            f"Context: {context}\n"
            "Please provide a comprehensive synthesis strategy for this molecule.\n"
            "Include:\n"
            "- Analysis of the target structure\n"
            "- Estimated number of synthetic steps\n"
            "- Key strategic steps and their rationale\n"
            "- Why this approach is optimal\n"
            "Keep your response to around 200 words in clear English."
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": 10000,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        return self._parse_strategy_response(raw, target_smiles=target_smiles, context=context)

    def parse_molecule(self, input_text: str, system_prompt: str) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            return self._fallback_parse_molecule(input_text)

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        user_prompt = (
            f"Input: {input_text}\n"
            "Task: Parse this molecule input and return a structured analysis.\n"
            "Output JSON must include:\n"
            "- canonical_smiles: str (valid SMILES)\n"
            "- valid: bool (whether structure is valid)\n"
            "- source_type: str (e.g., 'smiles', 'name')\n"
            "- fragmentable: bool (whether molecule can be fragmented)\n"
            "- fragment_count: int (estimated number of fragments)\n"
            "- fragment_confidence: float (0.0-1.0)\n"
            "- fragment_rationale: str (reasoning for fragment count)\n"
            "- strategy: str (recommended synthesis strategy)\n"
            "- risks: list[str] (potential risks)\n"
            "- hints: list[str] (disconnection hints)\n"
            "- scaffold_summary: str (scaffold description)\n"
            "- functional_groups: list[str] (functional groups present)\n"
            "- ring_systems: list[str] (ring systems present)\n"
            "- description: str (general description)"
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 10000,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        try:
            result = json.loads(raw)
            if isinstance(result, dict) and "choices" in result and result["choices"]:
                content = result["choices"][0].get("message", {}).get("content", "")
                # 提取 JSON 内容
                parsed = self._extract_any_json(content)
                if parsed:
                    return parsed
                return {
                    "canonical_smiles": input_text,
                    "valid": False,
                    "source_type": "unknown",
                    "fragmentable": False,
                    "fragment_count": 1,
                    "fragment_confidence": 0.0,
                    "fragment_rationale": "Failed to parse",
                    "strategy": "manual_review",
                    "risks": ["parse_failure"],
                    "hints": [],
                    "scaffold_summary": "Unknown",
                    "functional_groups": [],
                    "ring_systems": [],
                    "description": f"Failed to parse input: {input_text}"
                }
        except json.JSONDecodeError:
            pass
        return {
            "canonical_smiles": input_text,
            "valid": False,
            "source_type": "unknown",
            "fragmentable": False,
            "fragment_count": 1,
            "fragment_confidence": 0.0,
            "fragment_rationale": "Failed to parse",
            "strategy": "manual_review",
            "risks": ["parse_failure"],
            "hints": [],
            "scaffold_summary": "Unknown",
            "functional_groups": [],
            "ring_systems": [],
            "description": f"Failed to parse input: {input_text}"
        }

    def generate_forward_synthesis(self, target_smiles: str, context: str = "", temperature: float = 0.1, top_p: float = 0.9) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            return {
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.6,
                "route": self._fallback_forward_route(target_smiles),
                "reasoning": "Fallback heuristic route generation used because no model name is configured.",
            }

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        system_prompt = (
            "你是一名资深正合成规划助手，专注于有机化学路线设计。\n"
            "你的任务是针对输入目标分子，直接生成正合成路线：从可得起始原料逐步构建到目标产物。\n"
            "重要要求：\n"
            "1. 生成完整的正合成路线，步骤必须按从起始原料到目标产物的顺序排列。\n"
            "2. 每一步都要明确输入反应物（inputs）和生成产物（product_smiles）。\n"
            "3. 使用正合成表述，关注反应物到产物的构建过程，不要写 precursors、disconnection 或从目标回推。\n"
            "4. 确保所有分子都是有效的SMILES编码。\n"
            "5. SMILES编码规则：\n"
            "   - 使用标准SMILES格式，如C表示碳，O表示氧，N表示氮等\n"
            "   - 芳香族碳用小写c表示，脂肪族碳用大写C表示\n"
            "   - 化学键用特定符号表示：-（单键）、=（双键）、#（三键）\n"
            "   - 括号用于表示分支结构\n"
            "   - 环结构用数字标记连接点\n"
            "6. 基于分子的复杂程度，生成尽可能多且合理的合成步骤。\n"
            "7. 必须提供详细的正合成推理过程（reasoning），解释：\n"
            "   - 为什么这样逐步构建更合理\n"
            "   - 每一步选择的反应类型和条件\n"
            "   - 中间体稳定性与化学可行性\n"
            "   - 可能的副反应和注意事项\n"
            "请直接输出结果，不要使用思考模式，不要展示推理过程。\n"
            "你必须只输出一个合法 JSON 对象，禁止输出 Markdown、代码块、解释性前后缀、列表或额外文本。\n"
            "JSON 必须且只能包含以下键：route, reasoning, confidence, target_smiles, context。\n"
            "字段含义如下：\n"
            "- route: 为正合成路线步骤的 JSON 数组，每个步骤包含：step_index, input_smiles, product_smiles, reaction_type, conditions, rationale\n"
            "  其中 conditions 为该步反应条件的简短描述（试剂、溶剂、温度等，例如：'K2CO3, DMF, 80°C' 或 'Pd/C, H2, EtOH, rt'）\n"
            "- reasoning: 为详细的推理过程，包含合成策略、反应顺序、化学合理性等，必须提供详细内容\n"
            "- confidence: 为 0.0 到 1.0 的数值，表示路线的整体置信度\n"
            "- target_smiles: 原样回显目标\n"
            "- context: 原样回显上下文\n"
            "请严格按照上述格式输出，不要添加任何额外内容。\n"
            "特别注意：reasoning字段必须包含详细的推理过程，不能为空。"
        )
        user_prompt = (
            f"Target SMILES: {target_smiles}\n"
            f"Context: {context}\n"
            "任务：生成完整的正合成路线，包含从起始原料到目标分子的所有步骤。\n"
            "要求：\n"
            "1. 生成完整的正合成路线，包含多个步骤。\n"
            "2. 每一步都必须明确输入反应物和生成产物。\n"
            "3. 所有分子必须是有效的SMILES编码。\n"
            "4. 基于分子的复杂程度，生成尽可能多的合成步骤。\n"
            "5. 中等复杂程度的分子，合成路线应尽可能长。\n"
            "6. 提供详细的推理过程，解释每一步的合成策略和反应类型。\n"
            "7. 每一步必须包含 conditions 字段，格式为：试剂, 溶剂, 温度/时间（例如：'Pd(PPh3)4, K2CO3, DMF/H2O, 80°C, 12h' 或 'NaBH4, MeOH, 0°C→rt, 1h'）。\n"
            "\n"
            "输出格式示例（字段结构，内容须基于真实化学）：\n"
            '{"route": ['
            '{"step_index": 1, "input_smiles": ["CCO", "CC(=O)Cl"], '
            '"product_smiles": "CC(=O)OCC", "reaction_type": "esterification", '
            '"conditions": "Et3N, DCM, 0°C→rt, 2h", '
            '"rationale": "酰氯与醇在碱催化下发生酯化反应", "confidence": 0.85}'
            '], "reasoning": "详细推理...", "confidence": 0.82, '
            '"target_smiles": "回显输入", "context": "回显上下文"}\n'
            "\n"
            "保持输出紧凑且可解析，不要包含任何 Markdown 或代码块。"
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": 65535,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        return self._parse_response(raw, target_smiles=target_smiles, context=context)

    def evaluate_reaction_step(self, target: Any, route: Any, step: Any, system_prompt: str) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            raise ValueError("MODEL_API_NAME is required for HTTP provider")

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        user_prompt = (
            f"Target: {target.canonical_smiles}\n"
            f"Route: {route.route_id}\n"
            f"Step: {step.step_index}\n"
            f"Input SMILES: {step.input_smiles}\n"
            f"Product SMILES: {step.product_smiles}\n"
            f"Reaction Type: {step.reaction_type}\n"
            f"Conditions: {step.conditions}\n"
            f"Confidence: {step.confidence}\n"
            "Task: Evaluate this reaction step for feasibility and safety.\n"
            "Output JSON must include:\n"
            "- reaction_feasibility: float (0.0-1.0)\n"
            "- chemical_plausibility: float (0.0-1.0)\n"
            "- substrate_compatibility: float (0.0-1.0)\n"
            "- functional_group_tolerance: float (0.0-1.0)\n"
            "- condition_reasonableness: float (0.0-1.0)\n"
            "- side_reaction_risk: float (0.0-1.0)\n"
            "- evidence_strength: float (0.0-1.0)\n"
            "- overall_verdict: str (feasible, borderline, weak, implausible)\n"
            "- critical_comments: list[str]\n"
            "- failure_modes: list[str]\n"
            "- improvement_suggestions: list[str]"
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 10000,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        try:
            result = json.loads(raw)
            if isinstance(result, dict) and "choices" in result and result["choices"]:
                content = result["choices"][0].get("message", {}).get("content", "")
                parsed = self._extract_any_json(content)
                if parsed:
                    return parsed
        except json.JSONDecodeError:
            pass
        return {
            "reaction_feasibility": 0.5,
            "chemical_plausibility": 0.5,
            "substrate_compatibility": 0.5,
            "functional_group_tolerance": 0.5,
            "condition_reasonableness": 0.5,
            "side_reaction_risk": 0.5,
            "evidence_strength": 0.5,
            "overall_verdict": "borderline",
            "critical_comments": ["Failed to evaluate step"],
            "failure_modes": ["evaluation_failure"],
            "improvement_suggestions": ["Re-evaluate with more information"]
        }

    def evaluate_reaction_route(self, target: Any, route: Any, system_prompt: str) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            raise ValueError("MODEL_API_NAME is required for HTTP provider")

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        steps_info = "\n".join([f"Step {step.step_index}: {step.reaction_type} from {step.input_smiles} to {step.product_smiles}" for step in route.steps])
        user_prompt = (
            f"Target: {target.canonical_smiles}\n"
            f"Route: {route.route_id}\n"
            f"Steps:\n{steps_info}\n"
            "Task: Evaluate this entire synthesis route.\n"
            "Output JSON must include:\n"
            "- reaction_feasibility: float (0.0-1.0)\n"
            "- chemical_plausibility: float (0.0-1.0)\n"
            "- substrate_compatibility: float (0.0-1.0)\n"
            "- functional_group_tolerance: float (0.0-1.0)\n"
            "- condition_reasonableness: float (0.0-1.0)\n"
            "- side_reaction_risk: float (0.0-1.0)\n"
            "- evidence_strength: float (0.0-1.0)\n"
            "- overall_verdict: str (feasible, borderline, weak, implausible)\n"
            "- critical_comments: list[str]\n"
            "- failure_modes: list[str]\n"
            "- improvement_suggestions: list[str]"
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 10000,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        try:
            result = json.loads(raw)
            if isinstance(result, dict) and "choices" in result and result["choices"]:
                content = result["choices"][0].get("message", {}).get("content", "")
                parsed = self._extract_any_json(content)
                if parsed:
                    return parsed
        except json.JSONDecodeError:
            pass
        return {
            "reaction_feasibility": 0.0,
            "chemical_plausibility": 0.0,
            "substrate_compatibility": 0.0,
            "functional_group_tolerance": 0.0,
            "condition_reasonableness": 0.0,
            "side_reaction_risk": 1.0,
            "evidence_strength": 0.0,
            "overall_verdict": "implausible",
            "critical_comments": ["Failed to evaluate route"],
            "failure_modes": ["evaluation_failure"],
            "improvement_suggestions": ["Re-evaluate with more information"]
        }

    def compare_routes(self, target: Any, routes: List[Any], critical_assessments: Optional[List[Any]], system_prompt: str) -> Dict[str, Any]:
        if not self.config.base_url:
            raise ValueError("MODEL_API_BASE_URL is required for HTTP provider")
        if not self.config.model_name:
            raise ValueError("MODEL_API_NAME is required for HTTP provider")

        endpoint = self.config.base_url.rstrip("/") + self.config.render_api_path() + self.config.query_params()
        routes_info = "\n".join([f"Route {route.route_id}: {len(route.steps)} steps" for route in routes])
        user_prompt = (
            f"Target: {target.canonical_smiles}\n"
            f"Routes:\n{routes_info}\n"
            "Task: Compare these synthesis routes and rank them.\n"
            "Output JSON must include:\n"
            "- ranked_routes: list of objects with route_id, rank, comparison_score, robustness_score, feasibility_score, execution_readiness, key_strengths, key_weaknesses, comparative_notes\n"
            "- recommended_route_id: str\n"
            "- overall_summary: str"
        )
        payload = {
            "model": self.config.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 10000,
            "stream": False,
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
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise RuntimeError(self._classify_http_error(exc.code, body)) from exc
        except error.URLError as exc:
            raise RuntimeError(f"connection_error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("timeout_error: request timed out") from exc

        try:
            result = json.loads(raw)
            if isinstance(result, dict) and "choices" in result and result["choices"]:
                content = result["choices"][0].get("message", {}).get("content", "")
                parsed = self._extract_any_json(content)
                if parsed:
                    return parsed
        except json.JSONDecodeError:
            pass
        return {
            "ranked_routes": [],
            "recommended_route_id": None,
            "overall_summary": "Failed to compare routes"
        }

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

    @staticmethod
    def _extract_any_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract the first valid JSON object from text, handling markdown fences."""
        if not text:
            return None
        cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()
        for start in range(len(cleaned)):
            if cleaned[start] != '{':
                continue
            depth = 0
            for end in range(start, len(cleaned)):
                if cleaned[end] == '{':
                    depth += 1
                elif cleaned[end] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start:end + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break
        return None

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Extract the first valid JSON object from text, handling markdown fences."""
        if not text:
            return None
        # Strip markdown code fences
        cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
        # Find the outermost balanced { ... } that contains "route"
        for start in range(len(cleaned)):
            if cleaned[start] != '{':
                continue
            depth = 0
            for end in range(start, len(cleaned)):
                if cleaned[end] == '{':
                    depth += 1
                elif cleaned[end] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start:end + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and "route" in parsed and isinstance(parsed["route"], list):
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break
        return None

    def _parse_response(self, raw: str, target_smiles: str, context: str) -> Dict[str, Any]:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "proposal": raw.strip() or f"ofox-backed proposal for {target_smiles}",
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.5,
                "notes": "non-json response from model API",
                "precursors": self._generate_reasonable_precursors(target_smiles),
                "reaction_type": "unknown",
            }

        if isinstance(decoded, dict):
            content = None
            reasoning = None

            if "choices" in decoded and decoded["choices"]:
                message = decoded["choices"][0].get("message", {})
                content = message.get("content")
            elif "message" in decoded:
                message = decoded["message"]
                content = message.get("content")
                reasoning = message.get("thinking")
            elif "response" in decoded:
                content = decoded["response"]
                reasoning = decoded.get("thinking")

            if content or reasoning:
                raw_content = (content or "").strip()
                raw_reasoning = (reasoning or "").strip()

                # Try to extract route JSON from content first, then reasoning
                nested = self._extract_json_from_text(raw_content) or self._extract_json_from_text(raw_reasoning)
                if nested is not None:
                    nested.setdefault("target_smiles", target_smiles)
                    nested.setdefault("context", context)
                    nested.setdefault("provider", self.config.provider)
                    nested.setdefault("confidence", 0.6)
                    if not nested.get("reasoning"):
                        nested["reasoning"] = raw_reasoning or "模型生成了完整的合成路线推理过程"
                    nested["raw_response"] = decoded
                    return nested

                return {
                    "target_smiles": target_smiles,
                    "context": context,
                    "provider": self.config.provider,
                    "confidence": 0.5,
                    "reaction_type": "forward_synthesis",
                    "rationale": "模型生成了合成路线",
                    "input_smiles": self._generate_reasonable_precursors(target_smiles),
                    "product_smiles": target_smiles,
                    "reasoning": raw_reasoning,
                    "route": None,
                }

            return {
                "proposal": str(decoded.get("response", decoded))[:200],
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.5,
                "notes": "unrecognized response format",
                "precursors": self._generate_reasonable_precursors(target_smiles),
                "reaction_type": "unknown",
            }

        return {
            "proposal": f"ofox-backed proposal for {target_smiles}",
            "target_smiles": target_smiles,
            "context": context,
            "provider": self.config.provider,
            "confidence": 0.5,
            "notes": "unrecognized model response format",
            "precursors": self._generate_reasonable_precursors(target_smiles),
            "reaction_type": "unknown",
        }
        
    def _parse_strategy_response(self, raw: str, target_smiles: str, context: str) -> Dict[str, Any]:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "strategy": raw.strip() or f"Synthesis strategy for {target_smiles}",
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.5,
                "notes": "non-json response from model API",
            }

        if isinstance(decoded, dict):
            content = None

            if "choices" in decoded and decoded["choices"]:
                message = decoded["choices"][0].get("message", {})
                content = message.get("content")
            elif "message" in decoded:
                message = decoded["message"]
                content = message.get("content")
            elif "response" in decoded:
                content = decoded["response"]

            if content:
                raw_content = content.strip()
                return {
                    "strategy": raw_content,
                    "target_smiles": target_smiles,
                    "context": context,
                    "provider": self.config.provider,
                    "confidence": 0.8,
                }

            return {
                "strategy": str(decoded.get("response", decoded))[:500],
                "target_smiles": target_smiles,
                "context": context,
                "provider": self.config.provider,
                "confidence": 0.5,
                "notes": "unrecognized response format",
            }

        return {
            "strategy": f"Synthesis strategy for {target_smiles}",
            "target_smiles": target_smiles,
            "context": context,
            "provider": self.config.provider,
            "confidence": 0.5,
            "notes": "unrecognized model response format",
        }

    def _fallback_parse_molecule(self, input_text: str) -> Dict[str, Any]:
        return {
            "canonical_smiles": input_text,
            "valid": True,
            "source_type": "smiles" if re.fullmatch(r"[A-Za-z0-9@+\-\[\]\(\)=#\/\\%.:]+", input_text or "") else "unknown",
            "fragmentable": True,
            "fragment_count": 3,
            "fragment_confidence": 0.6,
            "fragment_rationale": "Heuristic fallback analysis",
            "strategy": "modular_assembly",
            "risks": [],
            "hints": ["amine/heteroaryl disconnection", "halogen-mediated coupling"],
            "scaffold_summary": "Heteroaryl bromide scaffold",
            "functional_groups": ["bromide", "heteroaromatic ring", "ether"],
            "ring_systems": ["heteroaromatic bicyclic"],
            "description": f"Heuristic analysis for {input_text}",
        }

    def _fallback_forward_route(self, target_smiles: str) -> list[Dict[str, Any]]:
        return [
            {
                "step_index": 1,
                "input_smiles": [target_smiles],
                "product_smiles": target_smiles,
                "reaction_type": "protective_heuristic",
                "conditions": "analysis_only",
                "rationale": "Fallback route placeholder for UI rendering.",
                "confidence": 0.6,
            }
        ]

    def _generate_reasonable_precursors(self, target_smiles: str) -> list:
        """Return empty list — fabricating fake SMILES as precursors produces invalid routes."""
        return []


def build_model_client(config: ModelAPIConfig) -> ModelClient:
    """Select an implementation based on the configured provider."""

    if config.provider.lower() in {"http", "api", "remote"}:
        return HttpModelClient(config)
    return MockModelClient(config)
