"""Notation packs (plan 06): convention as *configuration*, not a new syntax.

A problem declares ``notation: irodov | american | jee`` in front-matter. The pack is plain data
consumed by two readers: ``verify``'s ``notation.*`` checks (flag drift — e.g. ``\\mathbf`` under a
``\\vec`` tradition) and ``mtph prompt --notation`` (a ~20-line style card the AI loads so it writes
consistent LaTeX *by hand*). There is **no** expansion layer — the author only ever writes plain
LaTeX (invariant 3); the pack only checks and documents.
"""
from __future__ import annotations

from typing import Dict, Optional

# Each pack is the minimal data the checks + card need. ``vector_strict`` means the other vector
# command is *wrong* (flag it); when False (American), either is acceptable and only *mixing* both
# is flagged.
PACKS: Dict[str, dict] = {
    "irodov": {
        "tradition": "Soviet / Irodov–Landau",
        "vector": r"\vec",
        "vector_strict": True,
        "frames": ["K", "K'"],
        "gravity": "9.8",
        "symbols": {
            "current density": "j",
            "susceptibility": r"\varkappa",
            "viscosity": r"\eta",
            "frequency": r"\nu",
        },
        "style": "terse statements; minimal given data; SI with comma decimals in the original.",
    },
    "american": {
        "tradition": "US textbook",
        "vector": r"\mathbf",
        "vector_strict": False,  # \vec is also acceptable; only flag mixing both
        "frames": ["S", "S'"],
        "gravity": "9.8 or 9.81",
        "symbols": {
            "current density": "J",
            "susceptibility": r"\chi",
            "frequency": "f",
        },
        "style": "fuller prose; more data given; point decimals.",
    },
    "jee": {
        "tradition": "JEE Advanced (India)",
        "vector": r"\vec",
        "vector_strict": True,
        "frames": ["S", "S'"],
        "gravity": "10",
        "symbols": {
            "current density": "J",
            "susceptibility": r"\chi",
        },
        "style": "vec arrows with American symbols; g = 10 m/s^2 is common.",
    },
}


def pack(pack_id: str) -> Optional[dict]:
    return PACKS.get(pack_id)


def card(pack_id: str) -> str:
    """A compact human/AI style card for one pack (used by ``mtph prompt --notation``)."""
    p = PACKS.get(pack_id)
    if p is None:
        return f"# Notation: unknown pack {pack_id!r} (known: {', '.join(sorted(PACKS))})\n"
    other = r"\mathbf" if p["vector"] == r"\vec" else r"\vec"
    vec_rule = (f"vectors: `{p['vector']}` (do **not** use `{other}`)" if p["vector_strict"]
                else f"vectors: `{p['vector']}` preferred (`{other}` ok — but don't mix both)")
    syms = "; ".join(f"{k} `{v}`" for k, v in p["symbols"].items())
    return (
        f"# Notation pack: {pack_id} — {p['tradition']}\n"
        f"- {vec_rule}\n"
        f"- reference frames: `{p['frames'][0]}`, `{p['frames'][1]}`\n"
        f"- canonical symbols: {syms}\n"
        f"- gravity: g = {p['gravity']} m/s²\n"
        f"- style: {p['style']}\n"
        f"- Write **plain LaTeX** throughout — this card only sets the convention; "
        f"`mtph verify` flags drift.\n"
    )
