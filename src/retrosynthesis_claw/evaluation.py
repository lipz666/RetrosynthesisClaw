"""Evaluation agents for retrosynthesis quality control."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model_client import ModelClient
from .prompts import build_comparator_evaluator_system_prompt, build_critical_evaluator_system_prompt
from .types import CriticalReactionAssessment, MoleculeAnalysis, RouteCandidate, RouteComparisonItem, RouteComparisonResult, EvaluationBundle, SynthesisStep


@dataclass
class CriticalReactionEvaluator:
    model_client: ModelClient
    system_prompt: str = field(default_factory=build_critical_evaluator_system_prompt)

    def evaluate_step(self, target: MoleculeAnalysis, route: RouteCandidate, step: SynthesisStep) -> CriticalReactionAssessment:
        # 调用 LLM API 进行步骤评估
        result = self.model_client.evaluate_reaction_step(
            target=target,
            route=route,
            step=step,
            system_prompt=self.system_prompt
        )
        
        # 提取结果
        return CriticalReactionAssessment(
            target_id=target.canonical_smiles,
            route_id=route.route_id,
            step_id=f"step-{step.step_index}",
            reaction_feasibility=result.get("reaction_feasibility", 0.5),
            chemical_plausibility=result.get("chemical_plausibility", 0.5),
            substrate_compatibility=result.get("substrate_compatibility", 0.5),
            functional_group_tolerance=result.get("functional_group_tolerance", 0.5),
            condition_reasonableness=result.get("condition_reasonableness", 0.5),
            side_reaction_risk=result.get("side_reaction_risk", 0.5),
            evidence_strength=result.get("evidence_strength", 0.5),
            overall_verdict=result.get("overall_verdict", "borderline"),
            critical_comments=result.get("critical_comments", []),
            failure_modes=result.get("failure_modes", []),
            improvement_suggestions=result.get("improvement_suggestions", []),
            metadata={
                "llm_response": result
            }
        )

    def evaluate_route(self, target: MoleculeAnalysis, route: RouteCandidate) -> CriticalReactionAssessment:
        if not route.steps:
            return CriticalReactionAssessment(
                target_id=target.canonical_smiles,
                route_id=route.route_id,
                step_id=None,
                reaction_feasibility=0.0,
                chemical_plausibility=0.0,
                substrate_compatibility=0.0,
                functional_group_tolerance=0.0,
                condition_reasonableness=0.0,
                side_reaction_risk=1.0,
                evidence_strength=0.0,
                overall_verdict="implausible",
                critical_comments=["Route contains no explicit steps."],
                failure_modes=["empty_route"],
                improvement_suggestions=["Generate explicit retrosynthesis steps before evaluating the route."],
                metadata={"llm_response": None, "empty_route": True},
            )

        # 调用 LLM API 进行路线评估
        result = self.model_client.evaluate_reaction_route(
            target=target,
            route=route,
            system_prompt=self.system_prompt
        )
        
        # 提取结果
        return CriticalReactionAssessment(
            target_id=target.canonical_smiles,
            route_id=route.route_id,
            step_id=None,
            reaction_feasibility=result.get("reaction_feasibility", 0.0),
            chemical_plausibility=result.get("chemical_plausibility", 0.0),
            substrate_compatibility=result.get("substrate_compatibility", 0.0),
            functional_group_tolerance=result.get("functional_group_tolerance", 0.0),
            condition_reasonableness=result.get("condition_reasonableness", 0.0),
            side_reaction_risk=result.get("side_reaction_risk", 1.0),
            evidence_strength=result.get("evidence_strength", 0.0),
            overall_verdict=result.get("overall_verdict", "implausible"),
            critical_comments=result.get("critical_comments", []),
            failure_modes=result.get("failure_modes", []),
            improvement_suggestions=result.get("improvement_suggestions", []),
            metadata={
                "llm_response": result
            }
        )

    def _verdict(self, score: float) -> str:
        if score >= 0.78:
            return "feasible"
        if score >= 0.6:
            return "borderline"
        if score >= 0.4:
            return "weak"
        return "implausible"

    def _build_comments(self, target: MoleculeAnalysis, route: RouteCandidate, step: SynthesisStep, verdict: str, side_reaction_risk: float) -> List[str]:
        comments = [f"Route {route.route_id} step {step.step_index} is assessed as {verdict}."]
        if target.risk_flags:
            comments.append(f"Target risk flags may complicate execution: {', '.join(target.risk_flags)}.")
        if side_reaction_risk > 0.55:
            comments.append("Side-reaction risk is non-trivial and may dominate the outcome if conditions are not tightly controlled.")
        if not step.conditions:
            comments.append("The step lacks explicit conditions, reducing confidence in practical executability.")
        return comments

    def _failure_modes(self, target: MoleculeAnalysis, step: SynthesisStep) -> List[str]:
        modes = []
        if target.risk_flags:
            modes.append("target_structural_complexity")
        if len(step.input_smiles) > 1:
            modes.append("multicomponent_mixing_issues")
        if not step.conditions:
            modes.append("underspecified_conditions")
        return modes or ["limited_evidence"]

    def _improvements(self, target: MoleculeAnalysis, step: SynthesisStep, verdict: str) -> List[str]:
        suggestions = []
        if verdict in {"weak", "implausible"}:
            suggestions.append("Consider an alternative disconnection strategy.")
        if not step.conditions:
            suggestions.append("Specify reagent, solvent, and temperature conditions.")
        if target.risk_flags:
            suggestions.append("Protect or temporarily mask sensitive functionality before this step.")
        return suggestions or ["The proposal is acceptable but could benefit from stronger evidence."]

    def _route_comments(self, target: MoleculeAnalysis, route: RouteCandidate, step_assessments: List[CriticalReactionAssessment]) -> List[str]:
        comments = [f"Route {route.route_id} contains {len(route.steps)} steps with average critical feasibility judged conservatively."]
        if target.fragmentable:
            comments.append("The target appears fragmentable, so modular assembly is reasonable if early steps are robust.")
        if any(item.overall_verdict in {"weak", "implausible"} for item in step_assessments):
            comments.append("At least one step is chemically fragile enough to threaten the full route.")
        return comments


@dataclass
class RouteComparatorEvaluator:
    model_client: ModelClient
    system_prompt: str = field(default_factory=build_comparator_evaluator_system_prompt)

    def rank_routes(self, target: MoleculeAnalysis, routes: List[RouteCandidate], critical_assessments: Optional[List[CriticalReactionAssessment]] = None) -> RouteComparisonResult:
        # 调用 LLM API 进行路线比较
        result = self.model_client.compare_routes(
            target=target,
            routes=routes,
            critical_assessments=critical_assessments,
            system_prompt=self.system_prompt
        )
        
        # 提取结果
        items: List[RouteComparisonItem] = []
        for route_item in result.get("ranked_routes", []):
            items.append(RouteComparisonItem(
                route_id=route_item.get("route_id", ""),
                rank=route_item.get("rank", 0),
                comparison_score=route_item.get("comparison_score", 0.0),
                robustness_score=route_item.get("robustness_score", 0.0),
                feasibility_score=route_item.get("feasibility_score", 0.0),
                execution_readiness=route_item.get("execution_readiness", 0.0),
                key_strengths=route_item.get("key_strengths", []),
                key_weaknesses=route_item.get("key_weaknesses", []),
                comparative_notes=route_item.get("comparative_notes", ""),
                metadata={
                }
            ))
        
        recommended = result.get("recommended_route_id", None)
        summary = result.get("overall_summary", "No routes were available for comparison.")
        
        return RouteComparisonResult(
            target_id=target.canonical_smiles,
            ranked_routes=items,
            recommended_route_id=recommended,
            overall_summary=summary,
            metadata={
                "route_count": len(routes),
                "llm_response": result
            }
        )

    def _critical_score(self, critical: Optional[CriticalReactionAssessment]) -> float:
        if critical is None:
            return 0.0
        return (critical.reaction_feasibility + critical.chemical_plausibility + critical.substrate_compatibility + critical.functional_group_tolerance + critical.condition_reasonableness + (1.0 - critical.side_reaction_risk) + critical.evidence_strength) / 7.0

    def _robustness(self, route: RouteCandidate, critical: Optional[CriticalReactionAssessment]) -> float:
        step_count_bonus = min(len(route.steps) / 10.0, 0.15)
        critical_bonus = self._critical_score(critical) * 0.6
        route_bonus = min(route.feasibility_score, 1.0) * 0.25
        return max(0.0, min(1.0, critical_bonus + route_bonus + step_count_bonus))

    def _execution_readiness(self, route: RouteCandidate, critical: Optional[CriticalReactionAssessment]) -> float:
        confidence_mean = sum(step.confidence for step in route.steps) / len(route.steps) if route.steps else 0.0
        penalty = 0.15 if critical and critical.overall_verdict in {"weak", "implausible"} else 0.0
        return max(0.0, min(1.0, confidence_mean + (route.feasibility_score * 0.3) - penalty))

    def _strengths(self, target: MoleculeAnalysis, route: RouteCandidate, critical: Optional[CriticalReactionAssessment]) -> List[str]:
        strengths = []
        if route.steps:
            strengths.append("has explicit step structure")
        if target.fragmentable:
            strengths.append("matches modular target logic")
        if critical and critical.overall_verdict == "feasible":
            strengths.append("critical assessment supports execution")
        return strengths or ["limited but usable route"]

    def _weaknesses(self, target: MoleculeAnalysis, route: RouteCandidate, critical: Optional[CriticalReactionAssessment]) -> List[str]:
        weaknesses = []
        if not route.steps:
            weaknesses.append("no explicit steps")
        if critical and critical.overall_verdict in {"weak", "implausible"}:
            weaknesses.append("critical evaluator flagged chemistry risk")
        if target.risk_flags:
            weaknesses.append("target has structural risk flags")
        return weaknesses or ["no major weaknesses detected"]

    def _comparative_notes(self, target: MoleculeAnalysis, route: RouteCandidate, critical: Optional[CriticalReactionAssessment]) -> str:
        verdict = critical.overall_verdict if critical else "unassessed"
        return f"Route {route.route_id} ranks based on a balance of robustness, feasibility, and execution readiness; critical verdict={verdict}."

    def _summary(self, target: MoleculeAnalysis, items: List[RouteComparisonItem]) -> str:
        if not items:
            return "No routes were available for comparison."
        best = items[0]
        if len(items) == 1:
            return f"Only one route was available; route {best.route_id} is selected conservatively."
        return f"Route {best.route_id} ranks highest for target {target.canonical_smiles} because it offers the best robustness-to-risk balance among the candidate routes."


@dataclass
class EvaluationOrchestrator:
    model_client: ModelClient
    critical: CriticalReactionEvaluator = None  # type: ignore[assignment]
    comparator: RouteComparatorEvaluator = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.critical is None:
            self.critical = CriticalReactionEvaluator(model_client=self.model_client)
        if self.comparator is None:
            self.comparator = RouteComparatorEvaluator(model_client=self.model_client)

    def evaluate(self, target: MoleculeAnalysis, routes: List[RouteCandidate]) -> EvaluationBundle:
        critical_assessments: List[CriticalReactionAssessment] = []
        for route in routes:
            critical_assessments.append(self.critical.evaluate_route(target, route))
        route_comparison = self.comparator.rank_routes(target, routes, critical_assessments)
        summary = route_comparison.overall_summary
        return EvaluationBundle(critical_assessments=critical_assessments, route_comparison=route_comparison, summary=summary, metadata={"route_count": len(routes), "critical_count": len(critical_assessments)})
