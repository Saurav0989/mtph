"""Command-line interface: ``mtph validate | render | new | vendor-katex``."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from . import __version__
from .diagram.dsl import DiagramSyntaxError
from .diagram.plot import PlotError
from .params import resolve as _resolve_params
from .parser import MtphSyntaxError, load
from .render.html import render_html
from .validate import validate

app = typer.Typer(
    add_completion=False,
    help="mtph — author, validate and render .mtph math/physics problems.",
)

_TEMPLATES = {
    "physics": """---
mtph: "0.2"
id: my-problem
title: My physics problem
subject: physics
topic: mechanics
difficulty: 2
tags: [example]
---

State the problem here. Use inline math like $v_0$ and $\\theta$.

$$\\sum F = ma$$

```figure caption="A free-body diagram."
incline angle=30 length=6
mass m at=incline.mid size=0.9 label="m"
force from=m dir=down label="mg"
force from=m dir=perp-out label="N"
angle at=incline.base from=0 to=30 value="\\theta"
```

```answer type=expression
a = g\\sin\\theta
```

````solution
Resolve forces along the incline: $\\sum F_\\parallel = mg\\sin\\theta = ma$,
so $a = g\\sin\\theta$.
````
""",
    "math": """---
mtph: "0.2"
id: my-problem
title: My math problem
subject: math
topic: calculus
difficulty: 2
tags: [example]
---

Evaluate the integral.

$$\\int_0^1 x^2 \\, dx$$

```plot
x: -1..2
f(x) = x^2
mark: (1, 1) label="(1,1)"
grid: true
```

```answer type=expression
\\frac{1}{3}
```
""",
}


def _fail(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _repo_root() -> Optional[Path]:
    """The source checkout root (dir holding pyproject.toml) above this package, or None."""
    for p in Path(__file__).resolve().parents:
        if (p / "pyproject.toml").exists():
            return p
    return None


def _refresh_backend() -> None:
    """Reinstall the current source into the double-click viewer's backend venv (``~/.mtph/venv``).

    The native viewer renders with its own isolated mtph (it must live outside TCC-protected
    folders), so it drifts from your dev source. This rebuilds + force-reinstalls it in one step,
    so a new DSL command / block type shows up in the viewer instead of erroring as "unknown".
    """
    import subprocess

    root = _repo_root()
    if root is None:
        _fail("can't find the mtph source tree (no pyproject.toml above this package); "
              "run --refresh-backend from a source checkout (your dev `mtph`).")
    backend = Path.home() / ".mtph" / "venv"
    backend_pip = backend / "bin" / "pip"
    if not backend_pip.exists():
        _fail(f"no viewer backend venv at {backend}. Run `mtph install-viewer` from a home/pipx "
              "install of mtph first (it creates the backend the viewer app calls).")
    typer.echo(f"rebuilding mtph from {root} into {backend} …")
    r = subprocess.run(
        [str(backend_pip), "install", "--force-reinstall", "--no-deps", str(root)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _fail("backend reinstall failed:\n" + (r.stderr or r.stdout)[-1500:]
              + f"\n\nManual fallback:\n  {backend_pip} install --force-reinstall --no-deps {root}")
    ver = subprocess.run([str(backend / "bin" / "python"), "-c",
                          "import mtph; print(mtph.__version__)"], capture_output=True, text=True)
    typer.secho(f"✓ viewer backend refreshed (mtph {ver.stdout.strip() or '?'}). "
                "Reopen any open .mtph window.", fg=typer.colors.GREEN)


@app.command("validate")
def validate_cmd(
    files: List[Path] = typer.Argument(..., metavar="FILE...", help="One or more .mtph files."),
) -> None:
    """Parse and schema-validate .mtph files."""
    bad = 0
    for f in files:
        try:
            doc = load(f)
            errors = validate(doc)
        except (MtphSyntaxError, OSError) as e:
            typer.secho(f"✗ {f}: {e}", fg=typer.colors.RED)
            bad += 1
            continue
        if errors:
            bad += 1
            typer.secho(f"✗ {f}", fg=typer.colors.RED)
            for err in errors:
                typer.echo(f"    {err}")
        else:
            typer.secho(f"✓ {f}", fg=typer.colors.GREEN)
    if bad:
        _fail(f"\n{bad} file(s) failed validation.")
    typer.secho(f"\nAll {len(files)} file(s) valid.", fg=typer.colors.GREEN)


@app.command("verify")
def verify_cmd(
    file: Path = typer.Argument(..., help="The .mtph file to verify."),
    format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="json (default when piped) or human (default on a terminal).",
    ),
    checks: Optional[str] = typer.Option(
        None, "--checks", help="Comma-separated subset of check groups to run "
        "(schema,latex,figure,plot,prose,notation,content).",
    ),
) -> None:
    """Graduated verification: catches silent failures `validate` can't (plan 02).

    Returns a machine-parseable report (stable finding ids + fix hints) so an AI can check its
    own work. Exit code is non-zero only on an `error`; `warnings` and `unknown` exit 0.
    """
    import json
    import sys

    from .verify import verify as run_verify

    try:
        text = file.read_text(encoding="utf-8")
    except OSError as e:
        _fail(f"cannot read {file}: {e}")

    only = [c.strip() for c in checks.split(",")] if checks else None
    report = run_verify(text, path=str(file), checks=only)

    fmt = (format or ("human" if sys.stdout.isatty() else "json")).lower()
    if fmt == "json":
        typer.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif fmt == "human":
        _print_verify_human(report)
    else:
        _fail(f"unknown --format {fmt!r} (use json or human)")
    raise typer.Exit(code=report.exit_code)


_SEV_COLOR = {
    "error": typer.colors.RED,
    "warning": typer.colors.YELLOW,
    "info": typer.colors.BLUE,
    "ok": typer.colors.GREEN,
    "unknown": typer.colors.MAGENTA,
}


def _print_verify_human(report) -> None:
    top = report.status
    color = {"ok": typer.colors.GREEN, "warnings": typer.colors.YELLOW, "error": typer.colors.RED}[top]
    typer.secho(f"{report.file or '<stdin>'} — {top.upper()}", fg=color, bold=True)
    for c in report.checks:
        dot = _SEV_COLOR.get(c.status, typer.colors.WHITE)
        typer.echo("  " + typer.style(f"● {c.group}: {c.status}", fg=dot)
                   + (f"  ({c.message})" if c.message and not c.findings else ""))
        for f in c.findings:
            typer.secho(f"      [{f.severity}] {f.id}"
                        + (f" (line {f.line})" if f.line else ""), fg=_SEV_COLOR.get(f.severity))
            typer.echo(f"        {f.message}")
            if f.fix:
                typer.secho(f"        → {f.fix}", fg=typer.colors.CYAN)


@app.command("audit")
def audit_cmd(
    file: Path = typer.Argument(..., help="The .mtph file to audit."),
) -> None:
    """Verify the file, then add advisory structural nudges and the hard-problem checklist.

    Audit advice is informational — only a `verify` error sets a non-zero exit. The pillars a tool
    can't judge are printed as a checklist for you (the human)."""
    from .audit import CHECKLIST, advisories, mentor
    from .parser import parse
    from .verify import verify as run_verify

    try:
        text = file.read_text(encoding="utf-8")
    except OSError as e:
        _fail(f"cannot read {file}: {e}")

    report = run_verify(text, path=str(file))
    _print_verify_human(report)

    try:
        doc = parse(text)
        advice, notes = advisories(doc), mentor(doc)
    except MtphSyntaxError:
        advice, notes = [], []  # unparseable — verify already reported the parse error

    if notes:  # holistic, difficulty-aware — the mentor's read
        typer.secho("\nmentor's read:", bold=True)
        for n in notes:
            typer.secho(f"  ⚑ {n}", fg=typer.colors.MAGENTA)

    typer.secho("\nadvisories (heuristic):", bold=True)
    if advice:
        for a in advice:
            typer.secho(f"  [info] {a.id}: {a.message}", fg=typer.colors.BLUE)
            if a.fix:
                typer.secho(f"        → {a.fix}", fg=typer.colors.CYAN)
    else:
        typer.echo("  none — structure looks complete.")

    typer.secho("\nhard-problem checklist (a human must judge):", bold=True)
    for item in CHECKLIST:
        typer.echo(f"  □ {item}")
    raise typer.Exit(code=report.exit_code)


@app.command("inspect")
def inspect_cmd(
    file: Path = typer.Argument(..., help="The .mtph file to inspect."),
    figure: Optional[int] = typer.Option(
        None, "--figure", "-n", help="Inspect only the Nth figure (1-based); default: all."
    ),
    format: Optional[str] = typer.Option(
        None, "--format", "-f", help="json (default when piped) or human (default on a terminal).",
    ),
) -> None:
    """Print a figure's resolved scene as data — coordinates, anchors, overlaps (plan 03).

    Lets an AI place figure elements correctly without rendering an image: it reads where every
    named anchor landed, the logical extent, and any overlapping labels.
    """
    import json
    import sys

    from .diagram.dsl import DiagramSyntaxError
    from .diagram.inspect import inspect_figure
    from .parser import load as load_doc

    try:
        doc = load_doc(file)
    except (MtphSyntaxError, OSError) as e:
        _fail(f"parse error: {e}")

    figures = [b for b in doc.blocks if b.type == "figure"]
    if not figures:
        _fail("this file has no figure blocks to inspect.")
    if figure is not None:
        if not (1 <= figure <= len(figures)):
            _fail(f"--figure {figure} out of range (file has {len(figures)} figure(s))")
        figures = [figures[figure - 1]]

    results = []
    for idx, b in enumerate(figures, start=1):
        try:
            results.append({"figure": idx, **inspect_figure(_resolve_params(b.source, doc.meta))})
        except DiagramSyntaxError as e:
            results.append({"figure": idx, "error": str(e), "figure_line": getattr(e, "lineno", None)})

    fmt = (format or ("human" if sys.stdout.isatty() else "json")).lower()
    if fmt == "json":
        typer.echo(json.dumps(results if figure is None else results[0], indent=2, ensure_ascii=False))
    elif fmt == "human":
        _print_inspect_human(results)
    else:
        _fail(f"unknown --format {fmt!r} (use json or human)")


def _print_scene_human(r, indent: str = "  ") -> None:
    e = r["extent"]
    typer.echo(f"{indent}extent: x {e['minx']}..{e['maxx']},  y {e['miny']}..{e['maxy']}")
    if r["anchors"]:
        typer.echo(f"{indent}anchors:")
        for name, pt in r["anchors"].items():
            typer.echo(f"{indent}  {name} = ({pt[0]}, {pt[1]})")
    typer.echo(f"{indent}elements: {len(r['elements'])}")
    for d in r["diagnostics"]:
        if d["type"] == "label_overlap":
            typer.secho(f"{indent}⚠ labels {d['labels'][0]!r} and {d['labels'][1]!r} overlap "
                        f"(area {d['overlap']})", fg=typer.colors.YELLOW)


def _print_inspect_human(results) -> None:
    for r in results:
        typer.secho(f"figure {r['figure']}", fg=typer.colors.GREEN, bold=True)
        if "error" in r:
            typer.secho(f"  error: {r['error']}", fg=typer.colors.RED)
            continue
        if "panels" in r:  # multi-panel
            typer.echo(f"  layout: {r['layout']}, {len(r['panels'])} panels")
            for i, p in enumerate(r["panels"], start=1):
                label = f" — {p['title']}" if p.get("title") else ""
                typer.secho(f"  panel {i}{label}", fg=typer.colors.CYAN)
                _print_scene_human(p, indent="    ")
            continue
        _print_scene_human(r)


@app.command()
def render(
    file: Path = typer.Argument(..., help="The .mtph file to render."),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output path."),
    format: Optional[str] = typer.Option(
        None, "--format", "-f", help="html (default), png, or svg."
    ),
    no_answer: bool = typer.Option(False, "--no-answer", help="Omit the answer/solution section."),
    grid: bool = typer.Option(False, "--grid", help="Overlay a coordinate grid on figures (authoring aid)."),
    cdn: bool = typer.Option(False, "--cdn", help="Link KaTeX from a CDN instead of inlining it "
                             "(tiny HTML, needs network to view). HTML format only."),
    artifact: bool = typer.Option(False, "--artifact", help="Emit HTML for a Claude Artifact: "
                                  "KaTeX from cdnjs (the only host the artifact sandbox allows), "
                                  "lighter than inline. Paste into a claude.ai HTML artifact."),
    quiz: bool = typer.Option(False, "--quiz", help="Render the answer as an interactive self-quiz "
                              "(input + tolerance check / clickable choices, with a reveal)."),
) -> None:
    """Render a .mtph file to HTML (default), PNG, or SVG."""
    try:
        doc = load(file)
    except (MtphSyntaxError, OSError) as e:
        _fail(f"parse error: {e}")

    errors = validate(doc)
    if errors:
        typer.secho("validation errors:", fg=typer.colors.RED, err=True)
        for err in errors:
            typer.echo(f"    {err}", err=True)
        raise typer.Exit(code=1)

    fmt = (format or (output.suffix[1:] if output and output.suffix else "html")).lower()
    if output is None:
        output = file.with_suffix(f".{fmt}")

    try:
        if fmt == "html":
            katex_mode = "cdnjs" if artifact else "cdn" if cdn else "auto"
            output.write_text(
                render_html(doc, include_answer=not no_answer, grid=grid, katex=katex_mode, quiz=quiz),
                encoding="utf-8",
            )
        elif fmt in ("png", "svg"):
            from .render.export import export_document

            export_document(doc, output, fmt)
        else:
            _fail(f"unknown format {fmt!r} (use html, png, or svg)")
    except (DiagramSyntaxError, PlotError) as e:
        _fail(f"render error: {e}")
    except RuntimeError as e:
        _fail(str(e))

    typer.secho(f"wrote {output}", fg=typer.colors.GREEN)


@app.command("figure")
def figure_cmd(
    file: Path = typer.Argument(..., help="The .mtph file."),
    output: Optional[Path] = typer.Option(None, "-o", "--output",
                                           help="Output path (single figure); .svg or .png."),
    which: Optional[int] = typer.Option(None, "--figure", "-n", help="Render only the Nth figure (1-based)."),
    grid: bool = typer.Option(False, "--grid", help="Overlay a coordinate grid."),
    nudge: bool = typer.Option(False, "--nudge", help="Push overlapping labels apart in the output "
                               "(opt-in; never edits the source file)."),
) -> None:
    """Render only the figure(s) to standalone SVG (or PNG) — a fast figure-authoring loop (plan 03).

    PNG output (``-o fig.png``) uses the lightweight cairosvg rasterizer (``mtph[raster]``), no
    headless browser needed. ``--nudge`` separates overlapping labels in the rendered output.
    """
    from .diagram.compile_svg import compile_figure

    try:
        doc = load(file)
    except (MtphSyntaxError, OSError) as e:
        _fail(f"parse error: {e}")

    figures = [b for b in doc.blocks if b.type == "figure"]
    if not figures:
        _fail("this file has no figure blocks.")
    if which is not None:
        if not (1 <= which <= len(figures)):
            _fail(f"--figure {which} out of range (file has {len(figures)} figure(s))")
        figures = [(which, figures[which - 1])]
    else:
        figures = list(enumerate(figures, start=1))

    def _write(svg: str, out: Path) -> None:
        if out.suffix.lower() == ".png":
            from .render.raster import svg_to_png
            svg_to_png(svg, out)
        else:
            out.write_text(svg, encoding="utf-8")
        typer.secho(f"wrote {out}", fg=typer.colors.GREEN)

    try:
        if output is not None:
            if len(figures) != 1:
                _fail("-o needs a single figure; add --figure N or omit -o for auto-named files.")
            idx, b = figures[0]
            _write(compile_figure(_resolve_params(b.source, doc.meta), grid=grid, nudge=nudge), output)
        else:
            for idx, b in figures:
                _write(compile_figure(_resolve_params(b.source, doc.meta), grid=grid, nudge=nudge),
                       file.with_name(f"{file.stem}.fig{idx}.svg"))
    except DiagramSyntaxError as e:
        _fail(f"figure error: {e}")
    except RuntimeError as e:  # cairosvg not installed
        _fail(str(e))


@app.command()
def view(
    path: Path = typer.Argument(..., help="A .mtph file, or a folder of them (library)."),
    app_window: bool = typer.Option(False, "--app", help="Open in a native desktop window."),
    port: int = typer.Option(0, "--port", help="Port (0 = pick a free one)."),
    no_open: bool = typer.Option(False, "--no-open", help="Start the server but don't open a window."),
) -> None:
    """Open a .mtph file (or folder) in the live reader — the easy way to read problems."""
    import threading
    import webbrowser

    if not path.exists():
        _fail(f"no such file or folder: {path}")

    from .viewer.server import make_server

    httpd, url = make_server(path, port=port)
    kind = "library" if path.is_dir() else "reader"
    typer.secho(f"mtph {kind} running at {url}", fg=typer.colors.GREEN)
    typer.echo("Edits to the file refresh the view automatically. Press Ctrl+C to stop.")

    if app_window:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            import webview  # pywebview (optional extra)
        except ImportError:
            typer.secho(
                'native window needs pywebview ("pip install \\"mtph[app]\\""); opening browser instead.',
                fg=typer.colors.YELLOW,
            )
            if not no_open:
                webbrowser.open(url)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
            return
        webview.create_window(f"mtph — {path.name}", url, width=920, height=1120)
        webview.start()
        httpd.shutdown()
        return

    if not no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        typer.echo("\nstopped.")
        httpd.shutdown()


@app.command("dev")
def dev_cmd(
    file: Path = typer.Argument(..., help="The .mtph file to develop."),
    port: int = typer.Option(0, "--port", help="Port (0 = pick a free one)."),
    no_open: bool = typer.Option(False, "--no-open", help="Start the server but don't open a window."),
) -> None:
    """Author loop: a live-reload viewer + continuous `verify` feedback in the terminal (plan 03).

    Edits to the file refresh the browser automatically *and* re-run verification, so you see
    findings (with fixes) update as you type. One command instead of the edit/render/look cycle.
    """
    import threading
    import time
    import webbrowser

    from .verify import verify as run_verify
    from .viewer.server import make_server

    if not file.is_file():
        _fail(f"no such file: {file}")

    def verify_and_print() -> None:
        try:
            text = file.read_text(encoding="utf-8")
        except OSError as e:
            typer.secho(f"cannot read {file}: {e}", fg=typer.colors.RED)
            return
        typer.echo("")
        _print_verify_human(run_verify(text, path=str(file)))

    httpd, url = make_server(file, port=port)
    verify_and_print()
    typer.secho(f"\nmtph dev running at {url}", fg=typer.colors.GREEN)
    typer.echo("Edits reload the page and re-verify. Press Ctrl+C to stop.")

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if not no_open:
        webbrowser.open(url)

    try:
        last = file.stat().st_mtime
    except OSError:
        last = 0.0
    try:
        while True:
            time.sleep(0.4)
            try:
                m = file.stat().st_mtime
            except OSError:
                continue
            if m != last:
                last = m
                verify_and_print()
                typer.secho(f"\nmtph dev running at {url} — Ctrl+C to stop.", fg=typer.colors.GREEN)
    except KeyboardInterrupt:
        typer.echo("\nstopped.")
        httpd.shutdown()


@app.command()
def new(
    path: Path = typer.Argument(Path("problem.mtph"), help="Where to write the new file."),
    subject: str = typer.Option("physics", "--subject", "-s", help="physics or math."),
    template: Optional[str] = typer.Option(
        None, "--template", "-t",
        help="Scaffold a known problem shape (e.g. charged-oscillator). Use 'list' to see all."),
) -> None:
    """Scaffold a starter .mtph file. ``--template <id>`` gives a structurally-complete,
    verifiable skeleton for a common problem shape with content slots to fill."""
    if template:
        from .templates import TEMPLATES, template_ids

        if template == "list":
            typer.echo("templates: " + ", ".join(template_ids()))
            return
        if template not in TEMPLATES:
            _fail(f"unknown template {template!r}. Available: {', '.join(template_ids())}")
        content = TEMPLATES[template]
    else:
        if subject not in _TEMPLATES:
            _fail("subject must be 'physics' or 'math'")
        content = _TEMPLATES[subject]
    if path.exists():
        _fail(f"refusing to overwrite existing file: {path}")
    path.write_text(content, encoding="utf-8")
    typer.secho(f"created {path}", fg=typer.colors.GREEN)


@app.command()
def doctor(
    format: Optional[str] = typer.Option(None, "--format", "-f", help="human (default) or json."),
) -> None:
    """Report environment health: Python, mtph, KaTeX vendor status, and optional extras (with
    the exact install command for each missing one). Exits non-zero if the core can't render."""
    import json
    import sys

    from .health import health_report

    rep = health_report()
    fmt = (format or ("human" if sys.stdout.isatty() else "json")).lower()
    if fmt == "json":
        typer.echo(json.dumps(rep, indent=2))
    elif fmt == "human":
        typer.echo(f"python   {rep['python']}")
        typer.echo(f"mtph     {rep['mtph']}")
        k = rep["katex"]
        if k["vendored"]:
            typer.secho(f"katex    vendored (v{k['version']})", fg=typer.colors.GREEN)
        else:
            typer.secho("katex    NOT vendored — run `mtph init` (offline math won't render; "
                        "`mtph render --cdn` still works)", fg=typer.colors.RED)
        typer.echo("optional extras:")
        for name, e in rep["extras"].items():
            if e["installed"]:
                typer.secho(f"  ✓ {name:7} {e['feature']}", fg=typer.colors.GREEN)
            else:
                typer.secho(f"  ✗ {name:7} {e['feature']}", fg=typer.colors.YELLOW)
                typer.echo(f"      install: {e['install']}")
    else:
        _fail(f"unknown --format {fmt!r} (use human or json)")
    if not rep["ok"]:
        raise typer.Exit(code=1)


@app.command()
def prompt(
    notation: Optional[str] = typer.Option(
        None, "--notation", help="Author in this notation convention (e.g. irodov, american); "
        "adds a one-line directive — see §6 for the full guidance."),
    full: bool = typer.Option(
        False, "--full", help="Also append the condensed hard-problem doctrine (thesis/card.md)."),
) -> None:
    """Print the mtph authoring card to stdout, so a tool-using AI can load its instructions
    locally (no filesystem spelunking). The local answer to "teach an AI .mtph from cold"."""
    from ._docs import agents_md, card_md

    parts: List[str] = []
    if notation:
        from .notation import card as notation_card

        parts.append(notation_card(notation))
    try:
        parts.append(agents_md())
        if full:
            parts.append("\n\n---\n\n" + card_md())
    except FileNotFoundError as e:
        _fail(str(e))
    typer.echo("\n".join(parts))


@app.command()
def init() -> None:
    """One-shot setup: ensure KaTeX is vendored (it ships in the wheel; re-fetch only if missing),
    then run a self-test render. ``pip install mtph && mtph init`` is the quickstart."""
    from .parser import parse
    from .tools.fetch_katex import fetch, is_vendored

    if is_vendored():
        typer.secho("✓ KaTeX already vendored", fg=typer.colors.GREEN)
    else:
        typer.echo("vendoring KaTeX…")
        try:
            fetch()
            typer.secho("✓ KaTeX vendored", fg=typer.colors.GREEN)
        except Exception as e:  # offline / no network — degrade, don't fail hard
            typer.secho(f"✗ could not vendor KaTeX: {e}", fg=typer.colors.YELLOW)
            typer.echo("  math still works via CDN: `mtph render --cdn`.")

    try:
        html = render_html(parse(_TEMPLATES["physics"]), katex="auto")
    except Exception as e:
        typer.secho(f"✗ self-test render failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if "<main>" in html and len(html) > 500:
        typer.secho("✓ self-test render OK", fg=typer.colors.GREEN)
    else:
        typer.secho("✗ self-test render produced unexpected output", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("mtph is ready. Try:  mtph new problem.mtph  then  mtph dev problem.mtph",
                fg=typer.colors.GREEN, bold=True)


@app.command("open")
def open_cmd(
    path: str = typer.Argument(..., help="A .mtph file, or '-' to read the source from stdin."),
    no_open: bool = typer.Option(False, "--no-open", help="Render but don't launch a browser."),
    to_stdout: bool = typer.Option(False, "--stdout", help="Print reader HTML to stdout (for the native viewer)."),
) -> None:
    """Render a .mtph to a self-contained reader page and open it (used by Finder double-click).

    Reading from stdin (``-``) lets the Finder viewer pipe a file's contents in, so this never
    needs filesystem access to macOS-protected folders (Desktop/Documents/Downloads).
    """
    import re
    import sys
    import tempfile
    import webbrowser

    from .parser import parse
    from .render.reader import render_error, render_reader

    if path == "-":
        text = sys.stdin.read()
        name = "problem"
    else:
        p = Path(path)
        if not p.exists():
            _fail(f"no such file: {p}")
        text = p.read_text(encoding="utf-8")
        name = p.stem

    # Always produce *some* HTML — never crash to empty output, or a GUI viewer shows a blank
    # white page instead of a readable error.
    try:
        doc = parse(text)
        errors = validate(doc)
        if errors:
            html = render_error("Validation errors:\n  - " + "\n  - ".join(errors),
                                title=name, source_text=text)
        else:
            # static reader (toggles still work; no live-reload since no server)
            html = render_reader(doc, source_text=text, title=doc.title)
    except (MtphSyntaxError, DiagramSyntaxError, PlotError) as e:
        html = render_error(str(e), title=name, source_text=text)
    except Exception as e:  # never let the viewer go blank
        html = render_error(f"Unexpected error rendering this file:\n{e}",
                            title=name, source_text=text)

    if to_stdout:
        sys.stdout.write(html)
        return

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name) or "problem"
    out = Path(tempfile.gettempdir()) / f"mtph-{safe}.html"
    out.write_text(html, encoding="utf-8")
    if not no_open:
        webbrowser.open(out.as_uri())
    typer.secho(f"opened {out}", fg=typer.colors.GREEN)


@app.command("install-viewer")
def install_viewer(
    with_quicklook: bool = typer.Option(
        False, "--quicklook",
        help="Also build the spacebar Quick Look extension. Needs an Apple Developer signing "
             "identity to load (ad-hoc signatures are rejected by macOS).",
    ),
    refresh_backend: bool = typer.Option(
        False, "--refresh-backend",
        help="Just reinstall the current source into the viewer's backend venv (~/.mtph/venv) so "
             "it renders with the latest mtph; skip rebuilding the app.",
    ),
) -> None:
    """macOS: open .mtph files in a clean native window by double-clicking them (like a PDF)."""
    import platform
    import shutil
    import subprocess
    import sys

    if refresh_backend:
        _refresh_backend()
        return

    if platform.system() != "Darwin":
        _fail("install-viewer currently supports macOS only. Use `mtph view <file>` elsewhere.")

    mtph_bin = Path(sys.executable).with_name("mtph")
    if not mtph_bin.exists():
        mtph_bin = Path(sys.argv[0]).resolve()

    protected = ("/Desktop/", "/Documents/", "/Downloads/")
    if any(s in str(mtph_bin) for s in protected):
        typer.secho(
            "WARNING: mtph is installed under a macOS-protected folder:\n"
            f"  {mtph_bin}\n"
            "Finder apps can't read those. Install mtph outside Desktop/Documents/Downloads\n"
            "(e.g. a venv in your home folder, or pipx) and re-run `mtph install-viewer`.",
            fg=typer.colors.YELLOW,
        )

    app_path = Path.home() / "Applications" / "mtph Viewer.app"
    app_path.parent.mkdir(parents=True, exist_ok=True)

    native = False
    quicklook = False
    if shutil.which("swiftc"):
        from .viewer.macos import build_native_app

        try:
            build_native_app(mtph_bin, app_path)
            native = True
        except subprocess.CalledProcessError as e:
            typer.secho(f"native build failed:\n{e.stderr}\nfalling back to a browser launcher.",
                        fg=typer.colors.YELLOW)
        if native and with_quicklook:
            from .viewer.macos import build_quicklook_extension

            try:
                build_quicklook_extension(mtph_bin, app_path)
                quicklook = True
            except subprocess.CalledProcessError as e:
                typer.secho(f"Quick Look extension build failed (skipping):\n{e.stderr}",
                            fg=typer.colors.YELLOW)

    if not native:
        _build_applescript_app(mtph_bin, app_path)

    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
        "LaunchServices.framework/Support/lsregister"
    )
    if Path(lsregister).exists():
        subprocess.run([lsregister, "-f", str(app_path)], capture_output=True)

    ql_active = False
    if quicklook:
        appex = app_path / "Contents" / "PlugIns" / "mtphQuickLook.appex"
        subprocess.run(["pluginkit", "-a", str(appex)], capture_output=True)
        check = subprocess.run(["pluginkit", "-m", "-p", "com.apple.quicklook.preview"],
                               capture_output=True, text=True)
        ql_active = "dev.mtph.viewer.quicklook" in check.stdout

    how = "in its own window" if native else "in your browser"
    typer.secho(f"installed {app_path}  (opens .mtph {how})", fg=typer.colors.GREEN)
    if ql_active:
        typer.secho("Quick Look preview active — select a .mtph and press space.",
                    fg=typer.colors.GREEN)
    elif quicklook:
        typer.secho(
            "Quick Look preview built, but macOS declined to load it: preview extensions must be\n"
            "signed with an Apple Developer ID (ad-hoc signatures aren't accepted). Spacebar\n"
            "preview needs that. The double-click window works regardless.",
            fg=typer.colors.YELLOW,
        )
    if shutil.which("duti"):
        subprocess.run(["duti", "-s", "dev.mtph.viewer", "mtph", "all"], capture_output=True)
        typer.secho("Set as the default app for .mtph. Double-click any .mtph to open it.",
                    fg=typer.colors.GREEN)
    else:
        typer.echo(
            "\nMake it the default (once):\n"
            "  right-click any .mtph in Finder → Open With → Other… →\n"
            '  choose "mtph Viewer" (in ~/Applications) and tick "Always Open With".\n'
            "  (Or `brew install duti`, then re-run `mtph install-viewer` to automate this.)"
        )


def _build_applescript_app(mtph_bin: Path, app_path: Path) -> None:
    """Fallback when swiftc is unavailable: an AppleScript app that opens the reader in a browser."""
    import plistlib
    import shutil
    import subprocess
    import tempfile

    if app_path.exists():
        shutil.rmtree(app_path)
    script = (
        "on open theFiles\n"
        f'    set mtphBin to "{mtph_bin}"\n'
        "    repeat with f in theFiles\n"
        "        try\n"
        "            set theText to (read f as «class utf8»)\n"
        "        on error\n"
        "            set theText to (read f)\n"
        "        end try\n"
        '        do shell script ("echo " & quoted form of theText & '
        '" | " & quoted form of mtphBin & " open -")\n'
        "    end repeat\n"
        "end open\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        src = tf.name
    subprocess.run(["osacompile", "-o", str(app_path), src], check=True, capture_output=True, text=True)
    plist_path = app_path / "Contents" / "Info.plist"
    data = plistlib.loads(plist_path.read_bytes())
    data["CFBundleIdentifier"] = "dev.mtph.viewer"
    data["CFBundleName"] = "mtph Viewer"
    data["CFBundleDocumentTypes"] = [{
        "CFBundleTypeName": "mtph problem", "CFBundleTypeExtensions": ["mtph"],
        "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Owner",
        "LSItemContentTypes": ["dev.mtph.problem"],
    }]
    data["UTExportedTypeDeclarations"] = [{
        "UTTypeIdentifier": "dev.mtph.problem", "UTTypeDescription": "mtph problem",
        "UTTypeConformsTo": ["public.plain-text"],
        "UTTypeTagSpecification": {"public.filename-extension": ["mtph"]},
    }]
    plist_path.write_bytes(plistlib.dumps(data))


@app.command("vendor-katex")
def vendor_katex(version: Optional[str] = typer.Argument(None)) -> None:
    """Download KaTeX into the package for offline math rendering."""
    from .tools.fetch_katex import DEFAULT_VERSION, fetch

    fetch(version or DEFAULT_VERSION)


@app.command()
def version() -> None:
    """Print the mtph version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
