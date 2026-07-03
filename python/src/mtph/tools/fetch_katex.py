"""Vendor KaTeX into ``mtph/vendor/katex`` for offline math rendering.

Fetches the KaTeX CSS + JS + fonts once. The HTML renderer then inlines these assets so
rendered ``.mtph`` documents are fully self-contained (no CDN).

Two strategies, tried in order:

1. download the official ``katex.zip`` release over HTTPS (uses ``certifi`` CAs if present);
2. fall back to ``npm pack katex@<version>`` (robust cert handling) and extract ``dist/``.

Usage::

    python -m mtph.tools.fetch_katex            # default pinned version
    python -m mtph.tools.fetch_katex 0.16.11    # a specific version
"""
from __future__ import annotations

import io
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_VERSION = "0.16.11"
_RELEASE = "https://github.com/KaTeX/KaTeX/releases/download/v{v}/katex.zip"


def vendor_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "vendor" / "katex"


def is_vendored() -> bool:
    d = vendor_dir()
    return (d / "katex.min.css").is_file() and (d / "katex.min.js").is_file()


def _ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _write_members(dest: Path, items) -> None:
    """items: iterable of (relpath, bytes); relpath stripped to below katex/ or dist/."""
    for rel, data in items:
        for prefix in ("katex/", "dist/"):
            if prefix in rel:
                rel = rel.split(prefix, 1)[-1]
                break
        if not rel or rel.endswith("/"):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _via_https(dest: Path, version: str) -> bool:
    url = _RELEASE.format(v=version)
    print(f"downloading KaTeX {version} from {url} ...")
    try:
        ctx = _ssl_context()
        with urllib.request.urlopen(url, context=ctx) as resp:  # noqa: S310
            data = resp.read()
    except Exception as e:  # network / SSL failure -> caller falls back to npm
        print(f"  https fetch failed: {e}")
        return False
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        _write_members(dest, ((m, zf.read(m)) for m in zf.namelist()))
    return True


def _via_npm(dest: Path, version: str) -> bool:
    if not shutil.which("npm"):
        return False
    print(f"falling back to `npm pack katex@{version}` ...")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = subprocess.run(
                ["npm", "pack", f"katex@{version}", "--silent"],
                cwd=tmp, capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"  npm pack failed: {e}")
            return False
        tgz = next(Path(tmp).glob("*.tgz"), None)
        if tgz is None:
            name = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
            tgz = Path(tmp) / name if name else None
        if not tgz or not tgz.is_file():
            print("  npm pack produced no tarball")
            return False
        with tarfile.open(tgz, "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            _write_members(dest, ((m.name, tf.extractfile(m).read()) for m in members))
    return True


def fetch(version: str = DEFAULT_VERSION) -> Path:
    dest = vendor_dir()
    dest.mkdir(parents=True, exist_ok=True)
    if not (_via_https(dest, version) or _via_npm(dest, version)):
        raise RuntimeError(
            "could not vendor KaTeX. Install `certifi` (pip install certifi) for HTTPS, "
            "or ensure `npm` is on PATH, then re-run `python -m mtph.tools.fetch_katex`."
        )
    if not is_vendored():
        raise RuntimeError(f"fetch finished but expected files are missing under {dest}")
    print(f"vendored KaTeX into {dest}")
    return dest


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    fetch(argv[0] if argv else DEFAULT_VERSION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
