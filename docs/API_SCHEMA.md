# RetrosynthesisClaw API Schema

## POST /route

### Request

```json
{
  "target": "CCO",
  "top_k": 3,
  "debug": false
}
```

### Response

```json
{
  "result": {},
  "retrosynthesis_plan": {},
  "route_count": 0,
  "selected_route": null,
  "execution_fragments": [],
  "execution_status": "pending"
}
```

### `RetrosynthesisPlan`

| Field | Type | Required | Description |
|---|---|---:|---|
| `target` | `MoleculeAnalysis` | yes | Parsed and enriched target molecule |
| `routes` | `RouteCandidate[]` | yes | Candidate routes |
| `summary` | `string` | yes | Plan-level summary |
| `selected_route_id` | `string \| null` | no | Chosen route id |
| `selected_route_index` | `number \| null` | no | Chosen route index |
| `execution_fragments` | `ExecutionFragment[]` | no | Fragment execution timeline |
| `execution_status` | `string` | no | `pending` / `partial` / `completed` |
| `metadata` | `object` | no | Additional orchestration metadata |

### `ExecutionFragment`

| Field | Type | Required | Description |
|---|---|---:|---|
| `fragment_id` | `string` | yes | Fragment identifier |
| `fragment_smiles` | `string` | yes | Fragment SMILES |
| `order_index` | `number` | yes | Execution order |
| `strategy` | `string` | yes | Execution strategy |
| `dependencies` | `string[]` | no | Upstream dependency fragment ids |
| `instructions` | `string` | no | Human-readable instructions |
| `status` | `string` | no | Execution state |
| `confidence` | `number` | no | Execution confidence |
| `result` | `object` | no | Fragment execution result snapshot |
| `metadata` | `object` | no | Extra context |

### `FragmentExecutionTask`

| Field | Type | Required | Description |
|---|---|---:|---|
| `task_id` | `string` | yes | Task identifier |
| `route_id` | `string` | yes | Route identifier |
| `fragment_id` | `string` | yes | Fragment identifier |
| `fragment_smiles` | `string` | yes | Fragment SMILES |
| `target_smiles` | `string` | yes | Target SMILES |
| `execution_strategy` | `string` | yes | Execution strategy |
| `instructions` | `string` | yes | Execution instructions |
| `order_index` | `number` | no | Order within route |
| `dependencies` | `string[]` | no | Dependencies |
| `metadata` | `object` | no | Extra context |

### `FragmentExecutionResult`

| Field | Type | Required | Description |
|---|---|---:|---|
| `task_id` | `string` | yes | Task identifier |
| `route_id` | `string` | yes | Route identifier |
| `fragment_id` | `string` | yes | Fragment identifier |
| `status` | `string` | yes | `completed` / `partial` / `failed` |
| `executed_steps` | `SynthesisStep[]` | no | Steps executed during fragment handling |
| `notes` | `string` | no | Execution notes |
| `confidence` | `number` | no | Execution confidence |
| `outputs` | `object` | no | Structured outputs |
| `metadata` | `object` | no | Extra context |

## POST /fragment/execute

### Request

```json
{
  "task": {
    "task_id": "route-1:fragment-1",
    "route_id": "route-1",
    "fragment_id": "fragment-1",
    "fragment_smiles": "CCO",
    "target_smiles": "CCOC(=O)c1ccccc1",
    "execution_strategy": "sequential_execution",
    "instructions": "Construct fragment 1 first",
    "order_index": 1,
    "dependencies": [],
    "metadata": {}
  }
}
```

### Response

Returns `FragmentExecutionResult`.

## Frontend timeline

The UI renders `execution_fragments` as a fragment timeline showing:

- fragment order
- execution status
- strategy
- SMILES
- instructions
- confidence
- serialized result snapshot
