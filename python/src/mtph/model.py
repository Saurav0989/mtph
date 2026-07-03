"""The mtph document object model (DOM).

Typed block subtypes (which drive render dispatch) plus a ``Document`` wrapper.
``meta`` is kept as a plain dict so optional front-matter fields round-trip losslessly;
it is validated structurally by ``schema.json`` (see :mod:`mtph.validate`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Union


@dataclass
class ProseBlock:
    text: str
    type: str = "prose"

    def to_dom(self) -> Dict[str, Any]:
        return {"type": "prose", "text": self.text}


@dataclass
class MathBlock:
    latex: str
    type: str = "math"

    def to_dom(self) -> Dict[str, Any]:
        return {"type": "math", "latex": self.latex}


@dataclass
class FigureBlock:
    source: str
    caption: str | None = None
    type: str = "figure"

    def to_dom(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": "figure", "source": self.source}
        if self.caption:
            d["caption"] = self.caption
        return d


@dataclass
class PlotBlock:
    source: str
    caption: str | None = None
    type: str = "plot"

    def to_dom(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": "plot", "source": self.source}
        if self.caption:
            d["caption"] = self.caption
        return d


@dataclass
class AnswerBlock:
    """The answer (or one part's answer), authored as a body ```answer block."""

    value: str
    part: str | None = None
    answer_type: str = "expression"
    type: str = "answer"

    def to_dom(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": "answer", "value": self.value}
        if self.answer_type and self.answer_type != "expression":
            d["answer_type"] = self.answer_type
        if self.part:
            d["part"] = self.part
        return d


@dataclass
class SolutionBlock:
    """A worked solution authored as a body ```solution block; may contain nested blocks."""

    children: List["Block"] = field(default_factory=list)
    type: str = "solution"

    def to_dom(self) -> Dict[str, Any]:
        return {"type": "solution", "blocks": [c.to_dom() for c in self.children]}


Block = Union[ProseBlock, MathBlock, FigureBlock, PlotBlock, AnswerBlock, SolutionBlock]

_BLOCK_BUILDERS = {
    "prose": lambda d: ProseBlock(text=d.get("text", "")),
    "math": lambda d: MathBlock(latex=d.get("latex", "")),
    "figure": lambda d: FigureBlock(source=d.get("source", ""), caption=d.get("caption")),
    "plot": lambda d: PlotBlock(source=d.get("source", ""), caption=d.get("caption")),
    "answer": lambda d: AnswerBlock(
        value=d.get("value", ""), part=d.get("part"),
        answer_type=d.get("answer_type", "expression"),
    ),
    "solution": lambda d: SolutionBlock(children=[block_from_dom(b) for b in d.get("blocks", [])]),
}


def block_from_dom(d: Dict[str, Any]) -> Block:
    t = d.get("type")
    builder = _BLOCK_BUILDERS.get(t)
    if builder is None:
        raise ValueError(f"unknown block type: {t!r}")
    return builder(d)


@dataclass
class Document:
    """A parsed .mtph document."""

    mtph: str = "0.1"
    meta: Dict[str, Any] = field(default_factory=dict)
    blocks: List[Block] = field(default_factory=list)

    # -- DOM (de)serialisation ------------------------------------------------
    def to_dom(self) -> Dict[str, Any]:
        return {
            "mtph": self.mtph,
            "meta": dict(self.meta),
            "blocks": [b.to_dom() for b in self.blocks],
        }

    @classmethod
    def from_dom(cls, dom: Dict[str, Any]) -> "Document":
        return cls(
            mtph=dom.get("mtph", "0.1"),
            meta=dict(dom.get("meta", {})),
            blocks=[block_from_dom(b) for b in dom.get("blocks", [])],
        )

    # -- convenience ----------------------------------------------------------
    @property
    def title(self) -> str:
        return self.meta.get("title", "Untitled")

    @property
    def subject(self) -> str:
        return self.meta.get("subject", "")
