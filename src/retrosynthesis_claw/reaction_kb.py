"""Reaction knowledge base: maps reaction types to standard conditions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import SynthesisStep

# reaction_type (normalized) → standard lab conditions string
REACTION_CONDITIONS: dict[str, str] = {
    # C–C bond formation
    "suzuki_coupling":              "Pd(PPh3)4, K2CO3, DMF/H2O, 80°C, 12h",
    "suzuki":                       "Pd(PPh3)4, K2CO3, DMF/H2O, 80°C, 12h",
    "heck_reaction":                "Pd(OAc)2, PPh3, Et3N, DMF, 100°C",
    "heck":                         "Pd(OAc)2, PPh3, Et3N, DMF, 100°C",
    "negishi_coupling":             "Pd(PPh3)4, ZnCl2, THF, 60°C",
    "sonogashira_coupling":         "PdCl2(PPh3)2, CuI, Et3N, DMF, 60°C",
    "sonogashira":                  "PdCl2(PPh3)2, CuI, Et3N, DMF, 60°C",
    "grignard":                     "RMgX, THF, −78°C→rt, anhydrous",
    "grignard_reaction":            "RMgX, THF, −78°C→rt, anhydrous",
    "wittig":                       "Ph3P=CHR, THF, −78°C→rt",
    "wittig_reaction":              "Ph3P=CHR, THF, −78°C→rt",
    "aldol_condensation":           "NaOH aq., EtOH, 0°C→rt",
    "aldol":                        "LDA, THF, −78°C, then aldehyde",
    "diels_alder":                  "neat or toluene, 100–150°C, sealed tube",
    "diels_alder_reaction":         "neat or toluene, 100–150°C, sealed tube",
    "michael_addition":             "K2CO3, DMF, rt, 2h",
    "mannich_reaction":             "AcOH cat., EtOH, rt→60°C",
    "claisen_condensation":         "NaOEt, EtOH, reflux",
    "claisen_rearrangement":        "neat or xylene, 200°C",
    # C–N bond formation
    "buchwald_hartwig":             "Pd2(dba)3, XPhos, Cs2CO3, toluene, 100°C",
    "buchwald_hartwig_amination":   "Pd2(dba)3, XPhos, Cs2CO3, toluene, 100°C",
    "reductive_amination":          "NaBH3CN, MeOH/AcOH, rt, 12h",
    "amide_coupling":               "HATU, DIPEA, DMF, rt, 2h",
    "amide_bond_formation":         "HATU, DIPEA, DMF, rt, 2h",
    "gabriel_synthesis":            "KOH, EtOH; then H2NNH2, EtOH, reflux",
    # C–O bond formation
    "esterification":               "DCC or SOCl2, Et3N, DCM, 0°C→rt",
    "williamson_ether_synthesis":   "K2CO3, DMF, 60°C, 6h",
    "williamson_ether":             "K2CO3, DMF, 60°C, 6h",
    "mitsunobu":                    "DIAD, PPh3, THF, 0°C→rt",
    "mitsunobu_reaction":           "DIAD, PPh3, THF, 0°C→rt",
    # Oxidation / Reduction
    "oxidation":                    "KMnO4 or PCC, DCM, rt; or Swern conditions",
    "reduction":                    "LiAlH4, THF, 0°C→rt; or NaBH4, MeOH, 0°C",
    "hydrogenation":                "Pd/C (10%), H2 (1 atm), EtOH, rt",
    "catalytic_hydrogenation":      "Pd/C (10%), H2 (1 atm), EtOH, rt",
    "epoxidation":                  "mCPBA, DCM, 0°C→rt",
    "sharpless_epoxidation":        "Ti(OiPr)4, L-(+)-DIPT, TBHP, DCM, −20°C",
    "ozonolysis":                   "O3, DCM, −78°C; then Me2S workup",
    # Halogenation
    "halogenation":                 "NBS or NCS, CCl4, hν or AIBN, reflux",
    "bromination":                  "Br2 or NBS, DCM or CCl4, 0°C→rt",
    "chlorination":                 "SO2Cl2 or NCS, CCl4, 0°C→rt",
    "iodination":                   "I2, HNO3 cat., AcOH, rt",
    # Functional group interconversion
    "deprotection":                 "TFA/DCM (Boc) or H2/Pd (Cbz) or TBAF/THF (silyl)",
    "protection":                   "Boc2O, Et3N, DCM (amine); TBSCl, imidazole, DMF (alcohol)",
    "saponification":               "NaOH, EtOH/H2O, reflux, 2h",
    "hydrolysis":                   "HCl aq. or NaOH aq., reflux",
    "dehydration":                  "H2SO4 cat., toluene, reflux; or P2O5",
    "elimination":                  "KOH, EtOH, reflux",
    "substitution":                 "K2CO3, DMF, 80°C",
    "nucleophilic_substitution":    "K2CO3, DMF, 80°C",
    "electrophilic_aromatic_substitution": "AlCl3 cat., DCM, 0°C→rt",
    "nitration":                    "HNO3/H2SO4, 0°C",
    "sulfonation":                  "ClSO3H, DCM, 0°C; or SO3/H2SO4",
    "cyclization":                  "AcOH cat. or H2SO4, toluene, reflux",
    "ring_closure":                 "K2CO3, DMF, 80°C",
    "forward_synthesis":            "",  # generic fallback — no default
}


def _normalize_reaction_type(reaction_type: str) -> str:
    return reaction_type.lower().strip().replace(" ", "_").replace("-", "_")


def lookup_conditions(reaction_type: str) -> str | None:
    """Return standard conditions for a reaction type, or None if unknown."""
    key = _normalize_reaction_type(reaction_type)
    result = REACTION_CONDITIONS.get(key)
    if result is not None and result != "":
        return result
    # Substring match for partial names (e.g. "Suzuki" in "Suzuki-Miyaura coupling")
    for kb_key, conditions in REACTION_CONDITIONS.items():
        if kb_key and kb_key in key or key in kb_key:
            if conditions:
                return conditions
    return None


def enrich_conditions(step: "SynthesisStep") -> "SynthesisStep":
    """If the step has no conditions, fill in from the knowledge base."""
    if not step.conditions:
        kb = lookup_conditions(step.reaction_type)
        if kb:
            step.conditions = f"{kb} [KB]"
    return step
