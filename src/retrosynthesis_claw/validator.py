"""Route validation: SMILES validity, route continuity, and atom-count sanity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

try:
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    _RDKIT = True
except ImportError:
    _RDKIT = False

from .types import SynthesisStep


@dataclass
class StepIssue:
    step_index: int
    kind: str       # "invalid_smiles" | "discontinuous" | "atom_imbalance"
    detail: str


@dataclass
class ValidationReport:
    valid: bool
    issues: List[StepIssue] = field(default_factory=list)

    def summary(self) -> str:
        if self.valid:
            return "route OK"
        parts = [f"step {i.step_index} [{i.kind}]: {i.detail}" for i in self.issues]
        return "; ".join(parts)


def _heavy_atom_count(smiles: str) -> int | None:
    if not _RDKIT:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return mol.GetNumHeavyAtoms()


def _is_valid_smiles(smiles: str) -> bool:
    if not smiles:
        return False
    if not _RDKIT:
        # Lightweight heuristic when RDKit unavailable
        return bool(smiles) and not smiles.startswith("_") and " " not in smiles
    return Chem.MolFromSmiles(smiles) is not None


class RouteValidator:
    """Validate a list of SynthesisStep objects for chemical plausibility."""

    ATOM_IMBALANCE_THRESHOLD = 0.40  # allow up to 40% change in heavy-atom count per step

    def validate(self, steps: List[SynthesisStep]) -> ValidationReport:
        issues: List[StepIssue] = []

        for i, step in enumerate(steps):
            idx = step.step_index

            # 1. SMILES validity for all molecules in this step
            for smi in step.input_smiles:
                if not _is_valid_smiles(smi):
                    issues.append(StepIssue(idx, "invalid_smiles", f"input '{smi}' is not valid SMILES"))

            if not _is_valid_smiles(step.product_smiles):
                issues.append(StepIssue(idx, "invalid_smiles", f"product '{step.product_smiles}' is not valid SMILES"))

            # 2. Route continuity: previous product should appear among current inputs
            if i > 0:
                prev_product = steps[i - 1].product_smiles
                if prev_product and prev_product not in step.input_smiles:
                    # Canonicalize before giving up
                    canonical_prev = _canonicalize(prev_product)
                    canonical_inputs = [_canonicalize(s) for s in step.input_smiles]
                    if canonical_prev and canonical_prev not in canonical_inputs:
                        issues.append(StepIssue(
                            idx, "discontinuous",
                            f"previous product '{prev_product}' not found in inputs of step {idx}"
                        ))

            # 3. Atom-count sanity (only when RDKit available)
            if _RDKIT and step.input_smiles and step.product_smiles:
                total_input_atoms = sum(
                    c for s in step.input_smiles
                    if (c := _heavy_atom_count(s)) is not None
                )
                product_atoms = _heavy_atom_count(step.product_smiles)
                if total_input_atoms and product_atoms:
                    ratio = abs(product_atoms - total_input_atoms) / max(total_input_atoms, 1)
                    if ratio > self.ATOM_IMBALANCE_THRESHOLD:
                        issues.append(StepIssue(
                            idx, "atom_imbalance",
                            f"heavy-atom count changed by {ratio:.0%} "
                            f"(inputs={total_input_atoms}, product={product_atoms})"
                        ))

        return ValidationReport(valid=len(issues) == 0, issues=issues)


def _canonicalize(smiles: str) -> str | None:
    if not _RDKIT or not smiles:
        return smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)
