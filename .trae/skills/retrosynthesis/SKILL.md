---
name: "retrosynthesis"
description: "Performs retrosynthesis for organic molecules using the RetrosynthesisClaw framework. Invoke when user provides a molecule SMILES and asks for retrosynthesis or synthetic routes."
---

# Retrosynthesis Skill

This skill handles retrosynthesis tasks using the RetrosynthesisClaw framework. It generates synthetic routes for organic molecules by breaking them down into simpler precursors.

## When to Invoke

Invoke this skill when:
- User provides a molecule SMILES and asks for retrosynthesis
- User requests synthetic routes for a compound
- User wants to analyze the feasibility of synthesizing a molecule
- User needs to break down a complex molecule into simpler building blocks

## How to Use

1. **Provide a molecule SMILES** (e.g., `BrC1=C2CCCOC2=NC=C1`)
2. The skill will use the RetrosynthesisClaw framework to:
   - Parse and standardize the molecule
   - Generate retrosynthesis steps using a local LLM
   - Evaluate the feasibility of generated routes
   - Return the best synthetic route

## Output Format

The skill returns:
- Target molecule information (SMILES, canonical form)
- Step-by-step retrosynthesis route
- Reaction types for each step
- Precursors for each step
- Confidence scores for each step
- Overall feasibility score for the route

## Example Usage

```
User: BrC1=C2CCCOC2=NC=C1 请进行逆合成分析
Assistant: Using retrosynthesis skill...

## Retrosynthesis Result
Target: BrC1=C2CCCOC2=NC=C1
Canonical: Brc1ccnc2c1CCCO2

### Steps
1. Ester Hydrolysis: Brc1ccnc2c1CCCO2 → Brc1ccnc2c1COOH + CH3CH2OH
2. Substitution: Brc1ccnc2c1COOH → Brc1ccnc2c1 + COOH
3. Electrophilic Substitution: Brc1ccnc2c1 → c1ccnc2c1 (indole)

Feasibility: 86.67/100
```

## Technical Details

- **Framework**: RetrosynthesisClaw multi-agent system
- **Model**: Local Ollama qwen3:8b (keyless operation)
- **Steps**: Minimum 3 steps, maximum 5 steps per route
- **Scoring**: Based on reaction confidence and route length
- **Integration**: Uses local API for model inference

## Dependencies

- Python 3.9+
- RDKit (for molecule parsing)
- Ollama (local LLM service)
- FastAPI (optional, for API access)

## Limitations

- Requires local Ollama installation
- Limited to organic molecules that can be processed by the model
- Reaction predictions are based on model knowledge, not experimental data
- Complex molecules may require more computational time