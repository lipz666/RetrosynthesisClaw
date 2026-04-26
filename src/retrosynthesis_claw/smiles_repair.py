"""SMILES repair utilities with iterative retry support.

The repair pipeline is intentionally conservative:
- clean obvious text noise
- try RDKit validation/canonicalization
- fall back to name resolution if available
- retry up to `max_rounds` times using the latest repaired SMILES
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .chemistry import NameResolver

try:
    from rdkit import Chem
except Exception:  # pragma: no cover - optional dependency
    Chem = None


_CODE_FENCE_RE = re.compile(r"^```(?:json|smiles|txt)?\s*|\s*```$", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^(?:smiles\s*[:=]\s*|product\s*[:=]\s*|input\s*[:=]\s*)", re.IGNORECASE)
_ALLOWED_FRAGMENT_RE = re.compile(r"[A-Za-z0-9@+\-\[\]\(\)=#\\/%.]+")


@dataclass
class SmilesRepairResult:
    original: str
    repaired: str
    canonical_smiles: str
    valid: bool
    repaired_valid: bool
    strategy: str
    rounds_used: int
    confidence: float
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


def _strip_noise(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = _CODE_FENCE_RE.sub("", cleaned).strip()
    cleaned = cleaned.strip('"\'`')
    cleaned = _PREFIX_RE.sub("", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = cleaned.replace("；", ";").replace("，", ",").replace("。", ".")
    cleaned = cleaned.strip(" ,;:")
    # keep the first chemistry-like fragment if the model produced surrounding prose
    fragments = _ALLOWED_FRAGMENT_RE.findall(cleaned)
    if fragments:
        candidate = max(fragments, key=len)
        if len(candidate) >= 2:
            cleaned = candidate
    return cleaned


def _canonicalize(smiles: str) -> tuple[bool, str]:
    if Chem is None:
        return False, smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False, smiles
    return True, Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)


def _looks_like_name(text: str) -> bool:
    if not text:
        return False
    return not any(ch in text for ch in ("=", "#", "[", "]", "(", ")", "@")) and not any(ch.isdigit() for ch in text)


def repair_smiles(text: str, resolver: Optional[NameResolver] = None, max_rounds: int = 3) -> SmilesRepairResult:
    original = (text or "").strip()
    current = original
    issues: list[str] = []
    strategy = "failed"
    rounds_used = 0
    best_repaired = current
    best_canonical = current
    best_valid = False

    for round_idx in range(1, max_rounds + 1):
        rounds_used = round_idx
        candidate = _strip_noise(current)
        if candidate != current:
            issues.append(f"round_{round_idx}: stripped_text_noise")
        current = candidate

        valid, canonical = _canonicalize(current)
        if valid:
            strategy = "rdkit_canonicalize"
            best_repaired = current
            best_canonical = canonical
            best_valid = True
            break

        if resolver is not None and _looks_like_name(current):
            resolved = resolver.resolve(current)
            if resolved:
                issues.append(f"round_{round_idx}: resolved_name")
                current = resolved.strip()
                valid, canonical = _canonicalize(current)
                if valid:
                    strategy = "name_resolve_then_canonicalize"
                    best_repaired = current
                    best_canonical = canonical
                    best_valid = True
                    break
                issues.append(f"round_{round_idx}: resolved_name_but_invalid")

        # iterate again using the latest cleaned candidate
        if candidate == current:
            continue
        current = candidate

    confidence = 1.0 if strategy == "rdkit_canonicalize" else 0.85 if strategy == "name_resolve_then_canonicalize" else 0.0
    return SmilesRepairResult(
        original=original,
        repaired=best_repaired,
        canonical_smiles=best_canonical,
        valid=best_valid,
        repaired_valid=best_valid,
        strategy=strategy,
        rounds_used=rounds_used,
        confidence=confidence,
        issues=issues,
        metadata={"max_rounds": max_rounds},
    )
