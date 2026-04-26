"""Agent implementations for the retrosynthesis scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .chemistry import NameResolver, normalize_molecule, _normalize_smiles
from .config import AppConfig
from .model_client import ModelClient, build_model_client
from .prompts import build_evaluator_system_prompt, build_execution_system_prompt, build_parser_system_prompt, build_planner_system_prompt
from .reaction_kb import enrich_conditions
from .smiles_repair import repair_smiles
from .types import ExecutionFragment, FragmentExecutionResult, FragmentExecutionTask, MoleculeAnalysis, MoleculeSpec, RouteCandidate, RetrosynthesisPlan, SynthesisStep


@dataclass
class MoleculeParserAgent:
    model_client: ModelClient
    resolver: Optional[NameResolver] = None
    system_prompt: str = field(default_factory=build_parser_system_prompt)

    @classmethod
    def create_default(cls, config: AppConfig) -> "MoleculeParserAgent":
        return cls(model_client=build_model_client(config.model), resolver=None)

    def run(self, input_text: str) -> MoleculeAnalysis:
        # 调用 LLM API 进行分子解析
        result = self.model_client.parse_molecule(input_text, system_prompt=self.system_prompt)
        
        # 提取结果
        canonical_smiles = result.get("canonical_smiles", "")
        valid = result.get("valid", False)
        source_type = result.get("source_type", "smiles")
        fragmentable = result.get("fragmentable", False)
        fragment_count = result.get("fragment_count", 1)
        fragment_confidence = result.get("fragment_confidence", 0.5)
        fragment_rationale = result.get("fragment_rationale", "")
        strategy = result.get("strategy", "direct_build")
        risks = result.get("risks", [])
        hints = result.get("hints", [])
        scaffold_summary = result.get("scaffold_summary", "")
        functional_groups = result.get("functional_groups", [])
        ring_systems = result.get("ring_systems", [])
        
        # rdkit fallback: if LLM failed to parse, use local normalization
        if not valid or not canonical_smiles:
            norm = _normalize_smiles(input_text)
            if norm.valid:
                canonical_smiles = norm.canonical_smiles
                valid = True
                source_type = "smiles"

        # 构建 MoleculeAnalysis 对象
        return MoleculeAnalysis(
            input_text=input_text,
            source_type=source_type,
            smiles=canonical_smiles,
            canonical_smiles=canonical_smiles,
            valid=valid,
            description=result.get("description", f"Parsed molecule: {canonical_smiles}"),
            scaffold_summary=scaffold_summary,
            functional_groups=functional_groups,
            ring_systems=ring_systems,
            fragmentable=fragmentable,
            fragment_count_estimate=fragment_count,
            fragmentability_confidence=fragment_confidence,
            fragment_rationale=fragment_rationale,
            synthetic_complexity=strategy,
            disconnection_hints=hints,
            risk_flags=risks,
            recommended_strategy=strategy,
            metadata={
                "parser": "llm",
            }
        )


@dataclass
class SynthesisAgent:
    model_client: ModelClient
    resolver: Optional[NameResolver] = None

    @classmethod
    def create_default(cls, config: AppConfig) -> "SynthesisAgent":
        return cls(model_client=build_model_client(config.model))

    def generate_strategy(self, target: MoleculeSpec | MoleculeAnalysis, route_seed: int = 0, context: str = "", prior_strategies: Optional[List[str]] = None, temperature: float = 0.1, top_p: float = 0.9) -> Dict[str, Any]:
        prior_strategies = [s.strip() for s in (prior_strategies or []) if s and s.strip()]
        prior_context = "\n\nPrior route strategies to avoid repeating:\n" + "\n\n".join(f"Route {idx + 1}: {strategy}" for idx, strategy in enumerate(prior_strategies)) if prior_strategies else ""
        return self.model_client.generate_synthesis_strategy(target.canonical_smiles, context=f"seed={route_seed};mode=synthesis_strategy{';' + context if context else ''}{prior_context}", temperature=temperature, top_p=top_p)

    def run(self, target: MoleculeSpec | MoleculeAnalysis, min_steps: int, route_seed: int = 0, context: str = "", prior_strategies: Optional[List[str]] = None, temperature: float = 0.1, top_p: float = 0.9) -> List[SynthesisStep]:
        smiles_length = len(target.canonical_smiles)
        analysis_context = self._analysis_context(target)
        if smiles_length < 10:
            min_steps = 3
        elif smiles_length < 30:
            min_steps = 10
        else:
            min_steps = 15
        _ = min_steps
        proposal = self.model_client.generate_forward_synthesis(target.canonical_smiles, context=f"seed={route_seed};mode=forward_synthesis{';' + context if context else ''};analysis={analysis_context}", temperature=temperature, top_p=top_p)
        if isinstance(proposal.get("route"), list) and proposal["route"]:
            steps: List[SynthesisStep] = []
            for idx, step_data in enumerate(proposal["route"]):
                if not isinstance(step_data, dict):
                    continue
                inputs = step_data.get("input_smiles", step_data.get("reactants", []))
                inputs = inputs if isinstance(inputs, list) else []
                repaired_inputs, input_meta = self._repair_inputs(inputs)
                product_repair = repair_smiles(str(step_data.get("product_smiles", target.canonical_smiles)), resolver=self.resolver, max_rounds=3)
                steps.append(enrich_conditions(SynthesisStep(step_index=idx + 1, input_smiles=repaired_inputs, product_smiles=product_repair.canonical_smiles if product_repair.valid else str(step_data.get("product_smiles", target.canonical_smiles)), reaction_type=str(step_data.get("reaction_type", "forward_synthesis")), conditions=str(step_data.get("conditions", "")), confidence=max(0.0, min(1.0, float(step_data.get("confidence", 0.5)))), rationale=str(step_data.get("rationale", step_data.get("proposal", ""))), metadata={"source": "model", "route_seed": route_seed, "prompt_mode": "forward_synthesis", "molecule_complexity": "simple" if smiles_length < 10 else "medium" if smiles_length < 30 else "complex", "smiles_length": smiles_length, "steps_generated": len(proposal["route"]), "reasoning": proposal.get("reasoning", "")})))
            return steps
        return self._generate_steps_sequentially(target, max(min_steps, 2), route_seed, context, temperature, top_p)

    def _repair_inputs(self, inputs: List[str]):
        repaired_inputs, input_meta = [], []
        for raw_input in inputs:
            repair = repair_smiles(str(raw_input), resolver=self.resolver, max_rounds=3)
            repaired_inputs.append(repair.canonical_smiles if repair.valid else str(raw_input))
            input_meta.append(repair.__dict__)
        return repaired_inputs, input_meta

    def _generate_steps_sequentially(self, target: MoleculeSpec | MoleculeAnalysis, num_steps: int, route_seed: int = 0, context: str = "", temperature: float = 0.1, top_p: float = 0.9) -> List[SynthesisStep]:
        steps: List[SynthesisStep] = []
        current_product = target.canonical_smiles
        for idx in range(num_steps):
            proposal = self.model_client.generate_forward_synthesis(current_product, context=f"seed={route_seed};step={idx + 1};mode=single_step_forward_synthesis;{context};analysis={self._analysis_context(target)}", temperature=temperature, top_p=top_p)
            inputs = proposal.get("input_smiles") if isinstance(proposal.get("input_smiles"), list) else proposal.get("precursors")
            inputs = inputs if isinstance(inputs, list) else []
            repaired_inputs, input_meta = self._repair_inputs([str(x) for x in inputs])
            product_repair = repair_smiles(str(proposal.get("product_smiles", current_product)), resolver=self.resolver, max_rounds=3)
            steps.append(enrich_conditions(SynthesisStep(step_index=len(steps) + 1, input_smiles=repaired_inputs or [current_product], product_smiles=product_repair.canonical_smiles if product_repair.valid else current_product, reaction_type=str(proposal.get("reaction_type") or proposal.get("route_type") or proposal.get("type") or "forward_synthesis"), conditions=str(proposal.get("conditions", "")), confidence=max(0.0, min(1.0, float(proposal.get("confidence", 0.5)))), rationale=str(proposal.get("notes") or proposal.get("rationale") or proposal.get("proposal") or ""), metadata={"source": "model", "route_seed": route_seed, "prompt_mode": "single_step_forward_synthesis", "fallback_used": not bool(proposal.get("input_smiles"))})))
            current_product = product_repair.canonical_smiles if product_repair.valid else current_product
        return steps

    def _analysis_context(self, target: MoleculeSpec | MoleculeAnalysis) -> str:
        bits = []
        for key in ("description", "fragmentable", "fragment_count_estimate", "synthetic_complexity", "recommended_strategy"):
            value = getattr(target, key, None)
            if value not in (None, ""):
                bits.append(f"{key}={value}")
        for key in ("risk_flags", "disconnection_hints"):
            value = getattr(target, key, None)
            if value:
                bits.append(f"{key}={value}")
        return ";".join(bits)


@dataclass
class EvaluatorAgent:
    system_prompt: str = field(default_factory=build_evaluator_system_prompt)

    def run(self, steps: List[SynthesisStep]) -> float:
        if not steps:
            return 0.0
        return round(min((sum(step.confidence for step in steps) / len(steps)) + min(len(steps) / 20.0, 0.1), 1.0), 4)


@dataclass
class RoutePlannerAgent:
    system_prompt: str = field(default_factory=build_planner_system_prompt)

    def run(self, target: MoleculeSpec | MoleculeAnalysis, steps: List[SynthesisStep], score: float, route_index: int = 1) -> RouteCandidate:
        return RouteCandidate(route_id=f"route-{route_index}", target_smiles=target.canonical_smiles, steps=steps, total_score=round(score * 100, 2), feasibility_score=score, route_notes=[f"Generated by the scaffold planner (route {route_index}).", self.system_prompt.splitlines()[0]], metadata={"min_route_policy": True, "route_index": route_index})


@dataclass
class FragmentExecutionAgent:
    system_prompt: str = field(default_factory=build_execution_system_prompt)

    def build_execution_fragments(self, route: RouteCandidate, target: MoleculeAnalysis) -> List[ExecutionFragment]:
        fragments: List[ExecutionFragment] = []
        steps = list(route.steps or [])
        if not steps:
            return fragments
        for idx, step in enumerate(steps, start=1):
            dependencies = [f"fragment-{idx - 1}"] if idx > 1 else []
            fragments.append(ExecutionFragment(fragment_id=f"fragment-{idx}", fragment_smiles=step.product_smiles or target.canonical_smiles, order_index=idx, strategy=target.recommended_strategy or "sequential_execution", dependencies=dependencies, instructions=step.rationale or target.fragment_rationale, metadata={"route_id": route.route_id, "step_index": step.step_index, "reaction_type": step.reaction_type, "confidence": step.confidence}))
        return fragments

    def run(self, task: FragmentExecutionTask, route: Optional[RouteCandidate] = None) -> FragmentExecutionResult:
        if not task.fragment_smiles or not task.target_smiles:
            return FragmentExecutionResult(task_id=task.task_id, route_id=task.route_id, fragment_id=task.fragment_id, status="failed", notes="missing fragment or target SMILES", confidence=0.0, metadata={"system_prompt": self.system_prompt, "task": task.to_dict()})
        fragment_repair = repair_smiles(task.fragment_smiles, max_rounds=2)
        target_repair = repair_smiles(task.target_smiles, max_rounds=2)
        if not fragment_repair.valid or not target_repair.valid:
            return FragmentExecutionResult(task_id=task.task_id, route_id=task.route_id, fragment_id=task.fragment_id, status="failed", notes="invalid fragment or target structure", confidence=0.1, metadata={"system_prompt": self.system_prompt, "task": task.to_dict(), "fragment_repair": fragment_repair.__dict__, "target_repair": target_repair.__dict__})
        executed_steps: List[SynthesisStep] = []
        if route:
            for step in route.steps:
                if task.fragment_smiles in step.input_smiles or task.fragment_smiles == step.product_smiles:
                    executed_steps.append(step)
        else:
            executed_steps.append(SynthesisStep(step_index=1, input_smiles=[task.fragment_smiles], product_smiles=task.target_smiles, reaction_type=task.execution_strategy or "fragment_execution", conditions=task.instructions[:120], confidence=0.5, rationale="Best-effort execution from fragment task", metadata={"task_id": task.task_id}))
        status = "completed" if executed_steps else "partial"
        confidence = 0.8 if status == "completed" else 0.4
        return FragmentExecutionResult(task_id=task.task_id, route_id=task.route_id, fragment_id=task.fragment_id, status=status, executed_steps=executed_steps, notes=task.instructions, confidence=confidence, outputs={"fragment_smiles": fragment_repair.canonical_smiles, "target_smiles": target_repair.canonical_smiles}, metadata={"system_prompt": self.system_prompt, "task": task.to_dict()})
