import threading
import urllib.error
import urllib.request

from mtph.parser import load
from mtph.render.reader import render_gallery, render_reader
from mtph.viewer.server import make_server

from conftest import EXAMPLES_DIR, example_files


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_viewer_server_routes():
    httpd, url = make_server(EXAMPLES_DIR, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        code, body = _get(url)  # gallery
        assert code == 200 and "problem(s)" in body
        code, _ = _get(url + "view?path=loop-the-loop.mtph")  # reader
        assert code == 200
        code, _ = _get(url + "view?path=../../../../etc/hosts")  # traversal blocked
        assert code == 404
    finally:
        httpd.shutdown()


def test_render_reader_has_chrome():
    doc = load(EXAMPLES_DIR / "loop-the-loop.mtph")
    html = render_reader(doc, source_text="raw source", title=doc.title, katex="none")
    assert "<main>" in html
    assert "Reveal answer" in html       # this example has an answer
    assert "source-drawer" in html
    assert "raw source" in html          # source embedded for the drawer


def test_viewer_shows_error_not_blank_on_bad_figure(tmp_path):
    # A figure error must render an error page (HTTP 200), never crash to a blank/empty page.
    bad = tmp_path / "bad.mtph"
    bad.write_text(
        '---\nmtph: "0.1"\ntitle: Bad\nsubject: physics\n---\n\n'
        "```figure\nnonsense_command x=1\n```\n",
        encoding="utf-8",
    )
    httpd, url = make_server(tmp_path, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        code, body = _get(url + "view?path=bad.mtph")
        assert code == 200
        assert len(body) > 100 and ("error" in body.lower() or "couldn't" in body.lower())
    finally:
        httpd.shutdown()


def test_render_gallery_cards():
    items = [{"href": "/v", "title": "Demo", "subject": "physics", "difficulty": 3, "tags": ["a"]}]
    html = render_gallery(items, katex="none")
    assert "Demo" in html
    assert "★★★☆☆" in html               # difficulty stars
