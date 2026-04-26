"""Prepare noisy SMILES calibration data from USPTO500MT_train.csv.

This script:
1) reads reactants/products from the raw CSV
2) canonicalizes valid SMILES with RDKit
3) injects synthetic noise to create a repair task
4) writes train/validation CSV files plus a dataset summary JSON

Example:
    python smiles/prepare_smiles_data.py \
        --input smiles/data/raw/USPTO500MT_train.csv \
        --output-dir smiles/data/processed \
        --val-ratio 0.02 \
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    from rdkit import Chem
except Exception:  # pragma: no cover - optional dependency
    Chem = None


NOISE_ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789[]()=#@+-/\\.%")


@dataclass
class RecordSummary:
    source_rows: int = 0
    source_examples: int = 0
    valid_examples: int = 0
    invalid_examples: int = 0
    reactant_examples: int = 0
    product_examples: int = 0


def _canonicalize_smiles(smiles: str) -> str | None:
    if Chem is None or not smiles or not isinstance(smiles, str):
        return None
    smiles = smiles.strip()
    if not smiles:
        return None
    parts = [p for p in smiles.split(".") if p]
    if not parts:
        return None

    canonical_parts: list[str] = []
    for part in parts:
        mol = Chem.MolFromSmiles(part)
        if mol is None:
            return None
        canonical_parts.append(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True))

    # Sort components to make mixture targets deterministic for training.
    canonical_parts.sort()
    return ".".join(canonical_parts)



def _inject_noise(smiles: str, rng: random.Random, intensity: float = 0.12) -> str:
    if not smiles:
        return smiles

    chars = list(smiles)
    n_ops = max(1, int(math.ceil(len(chars) * intensity / 4)))

    for _ in range(n_ops):
        op = rng.choice(["delete", "insert", "substitute", "swap", "wrap_noise", "dot_noise"])

        if op == "delete" and len(chars) > 1:
            idx = rng.randrange(len(chars))
            del chars[idx]
        elif op == "insert":
            idx = rng.randrange(len(chars) + 1)
            chars.insert(idx, rng.choice(NOISE_ALPHABET))
        elif op == "substitute" and chars:
            idx = rng.randrange(len(chars))
            chars[idx] = rng.choice(NOISE_ALPHABET)
        elif op == "swap" and len(chars) > 2:
            idx = rng.randrange(len(chars) - 1)
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        elif op == "wrap_noise":
            chars = list(rng.choice(['"', "'", "`"]) + "".join(chars) + rng.choice(['"', "'", "`"]))
        elif op == "dot_noise":
            if "." in chars and rng.random() < 0.5:
                idx = rng.randrange(len(chars))
                chars.insert(idx, ".")
            elif len(chars) > 3:
                idx = rng.randrange(1, len(chars) - 1)
                chars.insert(idx, ".")

    noisy = "".join(chars)
    # Optional lightweight cleanup to mimic model-ish text outputs.
    if rng.random() < 0.3:
        noisy = f"SMILES: {noisy}"
    if rng.random() < 0.2:
        noisy = noisy + rng.choice([".", ";", "\n"])
    return noisy


def _build_examples(df: pd.DataFrame, rng: random.Random, source_col: str, summary: RecordSummary) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for _, row in df.iterrows():
        raw_value = row.get(source_col, "")
        if not isinstance(raw_value, str) or not raw_value.strip():
            summary.invalid_examples += 1
            continue

        canonical = _canonicalize_smiles(raw_value)
        summary.source_examples += 1
        if canonical is None:
            summary.invalid_examples += 1
            continue

        summary.valid_examples += 1
        if source_col == "reactants":
            summary.reactant_examples += 1
        else:
            summary.product_examples += 1

        noisy = _inject_noise(canonical, rng=rng)
        examples.append(
            {
                "input_smiles": noisy,
                "target_smiles": canonical,
                "source_column": source_col,
            }
        )
    return examples


def _split_records(records: list[dict[str, str]], val_ratio: float, seed: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = random.Random(seed)
    shuffled = records[:]
    rng.shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_ratio)) if shuffled else 0
    return shuffled[n_val:], shuffled[:n_val]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare noisy SMILES repair data.")
    parser.add_argument("--input", type=Path, default=Path(r"C:\Users\lpz\Desktop\RetrosynthesisClaw\smiles\data\raw\USPTO500MT_train.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"C:\Users\lpz\Desktop\RetrosynthesisClaw\smiles\data\processed"))
    parser.add_argument("--val-ratio", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rows", type=int, default=0, help="Optional row limit for debugging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    if args.max_rows and args.max_rows > 0:
        df = df.head(args.max_rows)

    summary = RecordSummary(source_rows=len(df))
    reactant_examples = _build_examples(df, rng, "reactants", summary)
    product_examples = _build_examples(df, rng, "products", summary)
    all_examples = reactant_examples + product_examples
    summary.source_examples = len(all_examples)

    if not all_examples:
        raise RuntimeError("No valid SMILES examples were produced from the input file.")

    train_records, val_records = _split_records(all_examples, args.val_ratio, args.seed)

    train_path = args.output_dir / "smiles_repair_train.csv"
    val_path = args.output_dir / "smiles_repair_val.csv"
    summary_path = args.output_dir / "dataset_summary.json"

    pd.DataFrame(train_records).to_csv(train_path, index=False)
    pd.DataFrame(val_records).to_csv(val_path, index=False)

    summary_payload = {
        "source_rows": summary.source_rows,
        "source_examples": summary.source_examples,
        "valid_examples": summary.valid_examples,
        "invalid_examples": summary.invalid_examples,
        "reactant_examples": summary.reactant_examples,
        "product_examples": summary.product_examples,
        "train_examples": len(train_records),
        "val_examples": len(val_records),
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "columns": {
            "input_smiles": "noisy SMILES produced by synthetic corruption",
            "target_smiles": "canonical RDKit SMILES used as gold target",
            "source_column": "reactants or products",
        },
        "noise_strategy": {
            "description": "character-level corruption plus light text-noise wrappers",
            "operations": ["delete", "insert", "substitute", "swap", "wrap_noise", "dot_noise"],
        },
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    print(f"Saved: {train_path}")
    print(f"Saved: {val_path}")
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()
