"""Chemistry utilities for molecule normalization and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
except Exception:  # pragma: no cover - optional dependency
    Chem = None
    Descriptors = None
    rdMolDescriptors = None


@dataclass
class MoleculeNormalizationResult:
    """Result of molecule normalization."""

    input_text: str
    input_type: str
    smiles: str
    canonical_smiles: str
    valid: bool
    notes: str = ""


@dataclass
class MoleculeExportResult:
    """Result of molecule export operations."""

    input_text: str
    smiles: str
    canonical_smiles: str
    isomeric_smiles: str
    iupac_name: str
    molecular_formula: str = ""
    molecular_weight: float | None = None
    valid: bool = False
    notes: str = ""


class NameResolver:
    """Resolve chemical names to SMILES.

    A real implementation can call OPSIN, PubChem, or another structure service.
    This scaffold keeps the interface in place and provides a safe fallback.
    """

    def resolve(self, name: str) -> Optional[str]:
        return None


class PubChemNameResolver(NameResolver):
    """Best-effort resolver using PubChem PUG REST."""

    def resolve(self, name: str) -> Optional[str]:
        if not name:
            return None
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name)}/property/CanonicalSMILES/JSON"
        try:
            with urlopen(url, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            props = payload["PropertyTable"]["Properties"]
            if props:
                return props[0].get("CanonicalSMILES")
        except Exception:
            return None
        return None


def _looks_like_smiles(text: str) -> bool:
    return any(ch in text for ch in ("=", "#", "[", "]", "(", ")", "@")) or any(ch.isdigit() for ch in text)


def _mol_from_smiles(raw: str):
    if Chem is None:
        return None
    return Chem.MolFromSmiles(raw)


def _normalize_smiles(raw: str) -> MoleculeNormalizationResult:
    if Chem is None:
        return MoleculeNormalizationResult(raw, "smiles", raw, raw, True, "rdkit unavailable")

    mol = Chem.MolFromSmiles(raw)
    if mol is None:
        return MoleculeNormalizationResult(raw, "smiles", raw, raw, False, "invalid smiles")

    canonical = Chem.MolToSmiles(mol, canonical=True)
    return MoleculeNormalizationResult(raw, "smiles", raw, canonical, True, "rdkit canonicalized")


def _normalize_name(raw: str, resolver: Optional[NameResolver] = None) -> MoleculeNormalizationResult:
    resolver = resolver or PubChemNameResolver()
    resolved = resolver.resolve(raw)
    if not resolved:
        return MoleculeNormalizationResult(raw, "name", raw, raw, False, "name-to-structure not configured")

    normalized = _normalize_smiles(resolved)
    normalized.input_text = raw
    normalized.input_type = "name"
    normalized.notes = f"resolved from name: {normalized.notes}"
    return normalized


def normalize_molecule(text: str, resolver: Optional[NameResolver] = None) -> MoleculeNormalizationResult:
    """Normalize a user-provided molecule string."""

    raw = text.strip()
    if not raw:
        return MoleculeNormalizationResult(text, "unknown", "", "", False, "empty input")

    if _looks_like_smiles(raw):
        return _normalize_smiles(raw)

    return _normalize_name(raw, resolver=resolver)


def export_molecule(text: str, resolver: Optional[NameResolver] = None) -> MoleculeExportResult:
    """Export molecule information for UI use."""

    normalized = normalize_molecule(text, resolver=resolver)
    mol = _mol_from_smiles(normalized.canonical_smiles)
    if mol is None:
        return MoleculeExportResult(
            input_text=text,
            smiles=normalized.smiles,
            canonical_smiles=normalized.canonical_smiles,
            isomeric_smiles=normalized.canonical_smiles,
            iupac_name=normalized.canonical_smiles or text,
            valid=normalized.valid,
            notes=normalized.notes,
        )

    canonical = Chem.MolToSmiles(mol, canonical=True)
    isomeric = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    formula = rdMolDescriptors.CalcMolFormula(mol) if rdMolDescriptors else ""
    weight = float(Descriptors.MolWt(mol)) if Descriptors else None
    iupac_name = _infer_iupac_name(mol, canonical, normalized.notes)

    return MoleculeExportResult(
        input_text=text,
        smiles=normalized.smiles,
        canonical_smiles=canonical,
        isomeric_smiles=isomeric,
        iupac_name=iupac_name,
        molecular_formula=formula,
        molecular_weight=weight,
        valid=normalized.valid,
        notes=normalized.notes,
    )


def _infer_iupac_name(mol, canonical_smiles: str, notes: str) -> str:
    try:
        query = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{quote(canonical_smiles)}/property/IUPACName/JSON"
        with urlopen(query, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        props = payload["PropertyTable"]["Properties"]
        if props:
            name = props[0].get("IUPACName")
            if name:
                return name
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
        pass
    except Exception:
        pass

    if Chem is not None:
        try:
            formula = rdMolDescriptors.CalcMolFormula(mol) if rdMolDescriptors else ""
            atoms = mol.GetNumAtoms()
            return f"unnamed-structure ({formula or canonical_smiles}; atoms={atoms})"
        except Exception:
            return canonical_smiles
    return canonical_smiles
