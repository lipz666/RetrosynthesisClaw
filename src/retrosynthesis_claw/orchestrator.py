"""Workflow orchestration for RetrosynthesisClaw."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, List, Optional, TypedDict

from .agents import FragmentExecutionAgent, MoleculeParserAgent, RoutePlannerAgent, SynthesisAgent
from .evaluation import EvaluationOrchestrator
from .config import AppConfig, load_default_config
from .types import ExecutionFragment, EvaluationBundle, FragmentExecutionResult, FragmentExecutionTask, MoleculeAnalysis, RouteCandidate, RetrosynthesisPlan, SynthesisStep
from .validator import RouteValidator


class OrchestrationState(str, Enum):
    INIT = "INIT"
    PARSE = "PARSE"
    GENERATE = "GENERATE"
    EVALUATE = "EVALUATE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    DONE = "DONE"


class OrchestrationEvent(TypedDict, total=False):
    type: str
    state: str
    message: str
    target: MoleculeAnalysis
    steps: List[SynthesisStep]
    score: float
    route: RouteCandidate
    routes: List[RouteCandidate]
    route_index: int
    route_count: int
    error: str
    plan: RetrosynthesisPlan
    execution: FragmentExecutionResult
    task: FragmentExecutionTask
    fragments: List[ExecutionFragment]


@dataclass
class RetrosynthesisOrchestrator:
    config: AppConfig
    parser: MoleculeParserAgent
    synthesis: SynthesisAgent
    planner: RoutePlannerAgent
    executor: FragmentExecutionAgent
    evaluation: EvaluationOrchestrator
    validator: RouteValidator = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.validator is None:
            self.validator = RouteValidator()

    @classmethod
    def create_default(cls) -> "RetrosynthesisOrchestrator":
        config = load_default_config()
        from .model_client import build_model_client
        model_client = build_model_client(config.model)
        return cls(config=config, parser=MoleculeParserAgent(model_client=model_client), synthesis=SynthesisAgent.create_default(config), planner=RoutePlannerAgent(), executor=FragmentExecutionAgent(), evaluation=EvaluationOrchestrator(model_client=model_client), validator=RouteValidator())

    def run(self, target_input: str, top_k: int = 3) -> RetrosynthesisPlan:
        plan: Optional[RetrosynthesisPlan] = None
        for event in self.iterate(target_input, top_k=top_k):
            if event.get("type") == "complete":
                plan = event.get("plan")
        if plan is not None:
            return plan
        target = self.parser.run(target_input)
        return RetrosynthesisPlan(target=target, routes=[], summary="No routes generated.", execution_status="failed", metadata={"top_k": top_k})

    def iterate(self, target_input: str, top_k: int = 3) -> Iterator[OrchestrationEvent]:
        state = OrchestrationState.INIT
        route_count = max(top_k, 1)
        yield {"type": "progress", "state": state.value, "message": "orchestrator initialized"}

        state = OrchestrationState.PARSE
        yield {"type": "progress", "state": state.value, "message": "parsing target input"}
        target = self.parser.run(target_input)
        yield {"type": "target", "state": state.value, "target": target}

        routes: List[RouteCandidate] = []
        prior_strategies: List[str] = []
        execution_fragments: List[ExecutionFragment] = []
        all_execution_results: List[FragmentExecutionResult] = []

        for route_index in range(1, route_count + 1):
            route_temperature = min(0.1 + 0.05 * (route_index - 1), 0.3)
            route_top_p = min(0.9 + 0.03 * (route_index - 1), 0.98)
            try:
                state = OrchestrationState.GENERATE
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": f"generating synthesis strategy for route {route_index}/{route_count}"}
                strategy = self.synthesis.generate_strategy(target, route_seed=route_index, context=f"route_index={route_index};route_count={route_count}", prior_strategies=prior_strategies, temperature=route_temperature, top_p=route_top_p)
                steps = self.synthesis.run(target, self.config.min_route_steps, route_seed=route_index, context=f"route_index={route_index};route_count={route_count}", prior_strategies=prior_strategies, temperature=route_temperature, top_p=route_top_p)
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": f"generated {len(steps)} steps", "steps": steps}

                validation = self.validator.validate(steps)
                validation_meta = {"valid": validation.valid, "issues": [{"step": i.step_index, "kind": i.kind, "detail": i.detail} for i in validation.issues]}
                if not validation.valid:
                    yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": f"validation warnings: {validation.summary()}"}

                state = OrchestrationState.PLAN
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": "assembling route candidate"}
                route = self.planner.run(target, steps, 0.5, route_index=route_index)
                route.metadata["validation"] = validation_meta
                route.metadata["synthesis_strategy"] = strategy.get("strategy", "")
                route.metadata["target_analysis"] = target.to_dict()
                route.metadata["selected_fragment_count"] = len(steps)

                state = OrchestrationState.EVALUATE
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": "evaluating route feasibility"}
                bundle = self.evaluation.evaluate(target, [route])
                critical = bundle.critical_assessments[0] if bundle.critical_assessments else None
                comparison = bundle.route_comparison
                score = route.feasibility_score if route.feasibility_score else (comparison.ranked_routes[0].comparison_score if comparison and comparison.ranked_routes else 0.0)
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": f"critical verdict={critical.overall_verdict if critical else 'n/a'}; comparison score={score}", "score": score, "evaluation": bundle}

                route.feasibility_score = score
                route.total_score = round(score * 100, 2)
                route.metadata["critical_assessment"] = critical.to_dict() if critical else None
                route.metadata["evaluation_bundle"] = bundle.to_dict()
                prior_strategies.append(str(strategy.get("strategy", "")))
                route.metadata["prior_strategy_count"] = len(prior_strategies) - 1
                routes.append(route)
                yield {"type": "route", "state": state.value, "route_index": route_index, "route_count": route_count, "route": route, "evaluation": bundle}

                state = OrchestrationState.EXECUTE
                fragments = self.executor.build_execution_fragments(route, target)
                execution_fragments.extend(fragments)
                yield {"type": "progress", "state": state.value, "route_index": route_index, "route_count": route_count, "message": f"prepared {len(fragments)} execution fragments", "fragments": fragments}

                route_execution_results: List[FragmentExecutionResult] = []
                for fragment in fragments:
                    task = FragmentExecutionTask(task_id=f"{route.route_id}:{fragment.fragment_id}", route_id=route.route_id, fragment_id=fragment.fragment_id, fragment_smiles=fragment.fragment_smiles, target_smiles=target.canonical_smiles, execution_strategy=fragment.strategy, instructions=fragment.instructions, order_index=fragment.order_index, dependencies=fragment.dependencies, metadata=fragment.metadata)
                    execution = self.executor.run(task, route)
                    route_execution_results.append(execution)
                    all_execution_results.append(execution)
                    fragment.status = execution.status
                    fragment.result = execution.to_dict()
                    fragment.confidence = execution.confidence
                    yield {"type": "execution", "state": state.value, "route_index": route_index, "route_count": route_count, "task": task, "execution": execution}

                route.metadata["execution_results"] = [result.to_dict() for result in route_execution_results]
                route.metadata["execution_status"] = "completed" if route_execution_results and all(result.status == "completed" for result in route_execution_results) else "partial" if route_execution_results else "not_started"
                route.metadata["fragment_timeline"] = [fragment.to_dict() for fragment in fragments]
            except Exception as exc:
                route = RouteCandidate(route_id=f"route-{route_index}", target_smiles=target.canonical_smiles, steps=[], total_score=0.0, feasibility_score=0.0, route_notes=[f"generation failed: {exc}"], metadata={"error": str(exc), "route_index": route_index})
                routes.append(route)
                yield {"type": "route", "state": OrchestrationState.PLAN.value, "route_index": route_index, "route_count": route_count, "route": route, "error": str(exc)}

        state = OrchestrationState.DONE
        selected_route_id = routes[0].route_id if routes else None
        plan = RetrosynthesisPlan(target=target, routes=routes, summary=f"Generated {len(routes)} candidate routes.", selected_route_id=selected_route_id, selected_route_index=1 if routes else None, execution_fragments=execution_fragments, execution_status="completed" if all_execution_results and all(result.status == "completed" for result in all_execution_results) else "partial" if all_execution_results else "pending", metadata={"min_route_steps": self.config.min_route_steps, "max_route_steps": self.config.max_route_steps, "branching_factor": self.config.max_branching_factor, "model_provider": self.config.model.provider, "target_valid": target.valid, "target_source_type": target.source_type, "target_notes": target.metadata.get("notes", ""), "top_k": top_k, "orchestration_states": [state.value for state in OrchestrationState], "execution_result_count": len(all_execution_results), "target_analysis": target.to_dict(), "target_parser_metadata": target.metadata, "critical_assessments": [assessment.to_dict() for assessment in getattr(bundle, 'critical_assessments', [])], "route_comparison": bundle.route_comparison.to_dict() if getattr(bundle, 'route_comparison', None) else None, "evaluation_bundle": bundle.to_dict() if bundle else None, "evaluation_summary": getattr(bundle, 'summary', '')})
        yield {"type": "complete", "state": state.value, "routes": routes, "target": target, "plan": plan, "evaluation": bundle}
