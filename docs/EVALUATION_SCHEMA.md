# Evaluation System Schema

This document defines the formal schema for the dual-module evaluation system used by RetrosynthesisClaw.

## Overview

The evaluation system is split into two layers:

1. **CriticalReactionEvaluator**
   - Performs critical, chemistry-first evaluation of a single reaction step or route.
   - Focuses on whether the reaction can happen and how well it is likely to work.

2. **RouteComparatorEvaluator**
   - Compares multiple candidate routes.
   - Produces a relative ranking based on feasibility, robustness, execution readiness, and risk.

The unified output is `EvaluationBundle`.

---

## 1. `CriticalReactionAssessment`

Represents a critical evaluation of one reaction step or route fragment.

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `target_id` | string | yes | Target molecule or planning context identifier |
| `route_id` | string | yes | Route identifier |
| `step_id` | string \| null | no | Optional step identifier when evaluating a single step |
| `reaction_feasibility` | number | yes | Can the reaction likely happen at all? 0.0–1.0 |
| `chemical_plausibility` | number | yes | Mechanistic / chemical logic score |
| `substrate_compatibility` | number | yes | Whether the substrates are suitable for the transformation |
| `functional_group_tolerance` | number | yes | Tolerance of relevant functional groups |
| `condition_reasonableness` | number | yes | Whether the stated conditions make sense |
| `side_reaction_risk` | number | yes | Risk score for undesired side reactions; higher means riskier |
| `evidence_strength` | number | yes | How strong the supporting evidence is |
| `overall_verdict` | string | yes | One of `feasible`, `borderline`, `weak`, `implausible` |
| `critical_comments` | array[string] | yes | Critical observations, including strengths and weaknesses |
| `failure_modes` | array[string] | yes | Likely failure mechanisms or weak points |
| `improvement_suggestions` | array[string] | yes | Ways to improve the reaction or route |
| `metadata` | object | no | Extra implementation data |

### Suggested interpretation

- `reaction_feasibility` answers whether the chemistry can happen.
- `chemical_plausibility` answers whether the proposal makes sense mechanistically.
- `side_reaction_risk` is intentionally risk-oriented: higher values indicate greater concern.

---

## 2. `RouteComparisonItem`

Represents one route in the ranked comparison result.

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `route_id` | string | yes | Route identifier |
| `rank` | integer | yes | 1 is best |
| `comparison_score` | number | yes | Relative ranking score |
| `robustness_score` | number | yes | Route robustness / stability |
| `feasibility_score` | number | yes | Route-level feasibility |
| `execution_readiness` | number | yes | How ready the route is for execution |
| `key_strengths` | array[string] | yes | Main advantages of this route |
| `key_weaknesses` | array[string] | yes | Main disadvantages of this route |
| `comparative_notes` | string | yes | Why this route ranks where it does |
| `metadata` | object | no | Extra implementation data |

---

## 3. `RouteComparisonResult`

Represents the route ranking output across multiple candidates.

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `target_id` | string | yes | Target identifier |
| `ranked_routes` | array[`RouteComparisonItem`] | yes | Sorted routes from best to worst |
| `recommended_route_id` | string \| null | no | Best route selected by the comparator |
| `overall_summary` | string | yes | Short explanation of the ranking outcome |
| `metadata` | object | no | Extra implementation data |

---

## 4. `EvaluationBundle`

Top-level evaluation output.

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `critical_assessments` | array[`CriticalReactionAssessment`] | yes | Step/route critical evaluations |
| `route_comparison` | `RouteComparisonResult` \| null | no | Cross-route comparison result |
| `summary` | string | yes | Human-readable summary of the evaluation |
| `metadata` | object | no | Extra implementation data |

---

## 5. Prompt design goals

### `CriticalReactionEvaluator`
The prompt should:
- be critical and conservative
- evaluate whether the reaction can occur and how well it can occur
- explicitly mention likely failure modes
- avoid inflated scores
- output structured judgment rather than generic praise

### `RouteComparatorEvaluator`
The prompt should:
- compare multiple routes against each other
- rank routes by reliability and execution value
- explain why one route is better than another
- prefer routes with better robustness and lower risk concentration

---

## 6. Recommended API shape

### Single critical evaluation
```json
{
  "target_id": "target-1",
  "route_id": "route-1",
  "step_id": "step-1",
  "reaction_feasibility": 0.72,
  "chemical_plausibility": 0.68,
  "substrate_compatibility": 0.75,
  "functional_group_tolerance": 0.60,
  "condition_reasonableness": 0.70,
  "side_reaction_risk": 0.40,
  "evidence_strength": 0.58,
  "overall_verdict": "borderline",
  "critical_comments": ["Mechanistically plausible but condition-sensitive."],
  "failure_modes": ["competitive hydrolysis", "low substrate stability"],
  "improvement_suggestions": ["Use milder conditions", "protect the sensitive group"]
}
```

### Route ranking response
```json
{
  "target_id": "target-1",
  "ranked_routes": [
    {
      "route_id": "route-2",
      "rank": 1,
      "comparison_score": 0.87,
      "robustness_score": 0.90,
      "feasibility_score": 0.84,
      "execution_readiness": 0.88,
      "key_strengths": ["stable intermediates", "high-confidence key step"],
      "key_weaknesses": ["slightly longer sequence"],
      "comparative_notes": "Best balance of robustness and practical execution."
    }
  ],
  "recommended_route_id": "route-2",
  "overall_summary": "Route 2 ranks highest because it is the most robust and execution-ready."
}
```

---

## 7. Implementation recommendation

A good implementation pattern is:

- `CriticalReactionEvaluator.evaluate(...) -> CriticalReactionAssessment`
- `RouteComparatorEvaluator.rank(...) -> RouteComparisonResult`
- `EvaluationOrchestrator.evaluate(...) -> EvaluationBundle`

This keeps the system modular and easy to extend.
