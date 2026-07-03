"""Standalone-SVG helpers for individual figure / plot blocks.

These need no browser — they wrap the pure-Python SVG compilers with an XML prolog so the
result is a valid ``.svg`` file. (Whole-document export, which also needs typeset math, lives
in :mod:`mtph.render.export` and uses a headless browser.)
"""
from __future__ import annotations

from ..diagram.compile_svg import compile_figure
from ..diagram.plot import compile_plot
from ..model import Document, FigureBlock, PlotBlock

_PROLOG = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'


def figure_to_svg(source: str) -> str:
    return _PROLOG + compile_figure(source)


def plot_to_svg(source: str) -> str:
    return _PROLOG + compile_plot(source)


def block_to_svg(block) -> str:
    if isinstance(block, FigureBlock):
        return figure_to_svg(block.source)
    if isinstance(block, PlotBlock):
        return plot_to_svg(block.source)
    raise ValueError(f"block of type {getattr(block, 'type', '?')!r} has no SVG form")


def document_svgs(doc: Document):
    """Yield ``(index, svg)`` for each figure/plot block in the document."""
    for i, b in enumerate(doc.blocks):
        if isinstance(b, (FigureBlock, PlotBlock)):
            yield i, block_to_svg(b)
