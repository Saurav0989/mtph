"""``mtph inspect`` — expose a figure's *resolved scene as data* (plan 03).

The compiler already resolves every command to logical coordinates; today that knowledge dies
inside the SVG string. ``inspect_figure`` surfaces it so an eyeless author (an AI) can check
placement, see where named anchors landed, and catch overlapping labels — all without rendering
a pixel (principle P2, "feedback over faith").

The same overlap engine feeds ``mtph verify``'s ``figure.label_overlap`` finding, so inspect and
verify can never disagree (principle P1).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from . import shapes as S
from .compile_svg import Compiler, _panelize

Bounds = Tuple[float, float, float, float]


def _r(x: float, n: int = 4) -> float:
    return round(x, n)


def _pt(p) -> List[float]:
    return [_r(p[0]), _r(p[1])]


def _bounds(bb: Optional[Bounds]) -> Optional[List[float]]:
    return [_r(bb[0]), _r(bb[1]), _r(bb[2]), _r(bb[3])] if bb else None


def _element(pr, bb: Optional[Bounds]) -> Dict[str, Any]:
    b = _bounds(bb)
    if isinstance(pr, S.Line):
        dx, dy = pr.p2[0] - pr.p1[0], pr.p2[1] - pr.p1[1]
        d: Dict[str, Any] = {
            "type": "arrow" if pr.arrow or pr.arrow_start else "line",
            "from": _pt(pr.p1), "to": _pt(pr.p2),
            "length": _r(math.hypot(dx, dy)),
            "angle_deg": _r(math.degrees(math.atan2(dy, dx)), 2),
        }
    elif isinstance(pr, S.Circle):
        d = {"type": "circle", "center": _pt(pr.c), "r": _r(pr.r)}
    elif isinstance(pr, S.Ellipse):
        d = {"type": "ellipse", "center": _pt(pr.c), "rx": _r(pr.rx), "ry": _r(pr.ry)}
    elif isinstance(pr, S.Text):
        d = {"type": "label", "text": pr.raw, "at": _pt(pr.pos)}
    elif isinstance(pr, S.Path):
        d = {"type": "path", "points": len(pr.points), "closed": pr.closed}
    elif isinstance(pr, S.BezPath):
        d = {"type": "bezpath", "segments": len(pr.segments)}
    else:
        d = {"type": type(pr).__name__.lower()}
    if b:
        d["bounds"] = b
    return d


def _overlap_area(a: Bounds, b: Bounds) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


_OVERLAP_EPS = 0.02  # logical units²; below this, labels merely touch — not worth a warning


def label_overlaps(labels: List[Tuple[str, Bounds]]) -> List[Dict[str, Any]]:
    """Pairwise label-box overlaps above a small threshold."""
    out: List[Dict[str, Any]] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            area = _overlap_area(labels[i][1], labels[j][1])
            if area > _OVERLAP_EPS:
                out.append({
                    "type": "label_overlap",
                    "labels": [labels[i][0], labels[j][0]],
                    "overlap": _r(area, 3),
                })
    return out


def _scene_dict(c: Compiler) -> Dict[str, Any]:
    """The resolved scene of one compiled figure as a plain dict."""
    scene = c.scene
    minx, miny, maxx, maxy = scene._bbox()

    anchors: Dict[str, List[float]] = {}
    for name, pt in c.points.items():
        anchors[name] = _pt(pt)
    for name, obj in c.objects.items():
        for part, pt in obj.get("anchors", {}).items():
            key = name if part == "center" else f"{name}.{part}"
            anchors.setdefault(key, _pt(pt))

    elements: List[Dict[str, Any]] = []
    labels: List[Tuple[str, Bounds]] = []
    for pr in scene.prims:
        bb = S.prim_bbox(pr)
        elements.append(_element(pr, bb))
        if isinstance(pr, S.Text) and bb:
            labels.append((pr.raw, bb))

    return {
        "extent": {"minx": _r(minx), "miny": _r(miny), "maxx": _r(maxx), "maxy": _r(maxy)},
        "anchors": anchors,
        "elements": elements,
        "diagnostics": label_overlaps(labels),
    }


def inspect_figure(source: str) -> Dict[str, Any]:
    """Compile a figure and return its resolved scene as a plain dict (JSON-ready).

    A multi-panel figure returns ``{"panels": [...], "elements": [...], "diagnostics": [...]}``
    with each panel inspected independently (its own coordinate space); a single-panel figure
    returns the flat ``extent``/``anchors``/``elements``/``diagnostics`` shape. Raises the same
    ``DiagramSyntaxError`` the compiler/renderer would, so callers see identical errors.
    """
    panels = _panelize(source)
    if panels is None:
        c = Compiler()
        c.execute(source)  # populates c.scene/points/objects (and would raise on bad input)
        return _scene_dict(c)

    layout, _cols, plist = panels
    out_panels: List[Dict[str, Any]] = []
    elements: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    for title, src in plist:
        c = Compiler()
        c.execute(src)
        d = _scene_dict(c)
        d["title"] = title
        out_panels.append(d)
        elements.extend(d["elements"])
        diagnostics.extend(d["diagnostics"])
    return {"layout": layout, "panels": out_panels,
            "elements": elements, "diagnostics": diagnostics}
