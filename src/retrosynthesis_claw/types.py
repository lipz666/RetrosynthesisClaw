"""Shared data structures for RetrosynthesisClaw."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MoleculeSpec:
    input_text: str
    smiles: str
    canonical_smiles: str
    source_type: str
    valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MoleculeAnalysis:
    input_text: str
    source_type: str
    smiles: str
    canonical_smiles: str
    valid: bool
    description: str
    scaffold_summary: str
    functional_groups: List[str] = field(default_factory=list)
    ring_systems: List[str] = field(default_factory=list)
    fragmentable: bool = False
    fragment_count_estimate: int = 0
    fragmentability_confidence: float = 0.0
    fragment_rationale: str = ""
    synthetic_complexity: str = "unknown"
    disconnection_hints: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    recommended_strategy: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesisStep:
    step_index: int
    input_smiles: List[str]
    product_smiles: str
    reaction_type: str
    conditions: str
    confidence: float
    rationale: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


RetrosynthesisStep = SynthesisStep


@dataclass
class RouteCandidate:
    route_id: str
    target_smiles: str
    steps: List[SynthesisStep]
    total_score: float
    feasibility_score: float
    route_notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"route_id": self.route_id, "target_smiles": self.target_smiles, "steps": [step.to_dict() for step in self.steps], "total_score": self.total_score, "feasibility_score": self.feasibility_score, "route_notes": self.route_notes, "metadata": self.metadata}


@dataclass
class ExecutionFragment:
    """Plan-level fragment descriptor used for execution timelines."""

    fragment_id: str
    fragment_smiles: str
    order_index: int
    strategy: str
    dependencies: List[str] = field(default_factory=list)
    instructions: str = ""
    status: str = "pending"
    confidence: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrosynthesisPlan:
    target: MoleculeAnalysis
    routes: List[RouteCandidate]
    summary: str
    selected_route_id: Optional[str] = None
    selected_route_index: Optional[int] = None
    execution_fragments: List[ExecutionFragment] = field(default_factory=list)
    execution_status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        routes = [route.to_dict() for route in self.routes]
        selected_route = next((route for route in routes if route["route_id"] == self.selected_route_id), None)
        return {"target": self.target.to_dict(), "summary": self.summary, "selected_route_id": self.selected_route_id, "selected_route_index": self.selected_route_index, "selected_route": selected_route, "routes": routes, "route_count": len(routes), "execution_fragments": [fragment.to_dict() for fragment in self.execution_fragments], "execution_status": self.execution_status, "metadata": self.metadata}


@dataclass
class FragmentExecutionTask:
    task_id: str
    route_id: str
    fragment_id: str
    fragment_smiles: str
    target_smiles: str
    execution_strategy: str
    instructions: str
    order_index: int = 0
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CriticalReactionAssessment:
    target_id: str
    route_id: str
    step_id: Optional[str]
    reaction_feasibility: float
    chemical_plausibility: float
    substrate_compatibility: float
    functional_group_tolerance: float
    condition_reasonableness: float
    side_reaction_risk: float
    evidence_strength: float
    overall_verdict: str
    critical_comments: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteComparisonItem:
    route_id: str
    rank: int
    comparison_score: float
    robustness_score: float
    feasibility_score: float
    execution_readiness: float
    key_strengths: List[str] = field(default_factory=list)
    key_weaknesses: List[str] = field(default_factory=list)
    comparative_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteComparisonResult:
    target_id: str
    ranked_routes: List[RouteComparisonItem]
    recommended_route_id: Optional[str] = None
    overall_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationBundle:
    critical_assessments: List[CriticalReactionAssessment] = field(default_factory=list)
    route_comparison: Optional[RouteComparisonResult] = None
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FragmentExecutionResult:
    task_id: str
    route_id: str
    fragment_id: str
    status: str
    executed_steps: List[SynthesisStep] = field(default_factory=list)
    notes: str = ""
    confidence: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "route_id": self.route_id, "fragment_id": self.fragment_id, "status": self.status, "executed_steps": [step.to_dict() for step in self.executed_steps], "notes": self.notes, "confidence": self.confidence, "outputs": self.outputs, "metadata": self.metadata}


@dataclass
class RoutePlan:
    target: MoleculeSpec
    routes: List[RouteCandidate]
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    recommended_route_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        routes = [route.to_dict() for route in self.routes]
        primary_route = routes[0] if routes else None
        synthesis_route = {"target": asdict(self.target), "recommended_route_id": self.recommended_route_id, "summary": self.summary, "routes": routes, "route_count": len(routes), "metadata": self.metadata}
        return {"target": asdict(self.target), "routes": routes, "synthesis_route": synthesis_route, "summary": self.summary, "metadata": self.metadata, "recommended_route_id": self.recommended_route_id, "route_count": len(routes), "primary_route": primary_route}
