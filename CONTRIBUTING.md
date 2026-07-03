# Contributing to mtph

Thanks for your interest! mtph is in early development — format **v0.2**, Python reference
implementation. Issues and PRs are welcome.

## Repo layout

```
spec/         The format: SPEC.md, schema.json, examples/
thesis/       The doctrine of hard-problem design (phythesis.md)
AGENTS.md     The AI authoring manual
python/       The reference implementation: python/src/mtph (package) + python/tests
pyproject.toml  Packaging (at the repo root)
```

## Dev setup

```bash
git clone https://github.com/Saurav0989/mtph && cd mtph
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # editable install + test deps
pytest                          # should be all green
```

KaTeX is committed under `python/src/mtph/vendor/katex`, so math renders offline with no extra
step. To update it: `python -m mtph.tools.fetch_katex` (re-vendors, then commit the result).

Optional extras for the full toolchain:

```bash
pip install -e ".[export]" && playwright install chromium   # PNG/SVG export
pip install -e ".[app]"                                     # native viewer window
```

## Ground rules

- **`spec/schema.json` is the source of truth.** Any change to the data model updates the
  schema *and* `SPEC.md` together. A future JS implementation must validate against the same
  schema, so keep it implementation-neutral.
- **A new DSL command or block type needs four things:** a `SPEC.md` entry, a compiler/renderer
  implementation, an entry in `AGENTS.md` (so AIs know it exists), and a test.
- Keep core dependencies minimal; heavy/optional features (PNG export, native window) go behind
  extras.
- The renderer must **never crash to empty output** — any error renders a readable error page
  (so a GUI viewer never shows a blank screen). There's a regression test for this.
- Run `pytest` before opening a PR. Render an example and *look* at it if you touched rendering.

## Building a release artifact

```bash
pip install build
python -m build            # writes dist/mtph-*.whl and dist/mtph-*.tar.gz
```

CI runs the test suite on every push/PR. To cut a release, bump `version` in `pyproject.toml`
and push a matching tag (e.g. `v0.2.0`); the release workflow then builds and publishes to PyPI.
(The `PYPI_API_TOKEN` repo secret is already configured — `v0.1.0` is [live on PyPI](https://pypi.org/project/mtph/).)
