# mtph playground

A zero-server, single-page editor for `.mtph`. Type a problem on the left, watch it render on the
right — LaTeX (KaTeX from cdnjs), figures and plots (the diagram DSL), the whole document. It runs
**entirely in the browser** on the JavaScript port (`js/`): `parse` → `validate` → `renderHtml`,
no backend.

**Share links carry their own source.** "Copy share link" lz-string-compresses the editor
contents into the URL fragment (`#…`). Nothing is uploaded or stored; opening the link
decompresses it back into the editor. Every shared problem is also its own source.

## Run it locally

The page loads a single bundled script, `playground/app.js`, built from `js/web/app.ts`:

```bash
cd js && npm install && npm run build:web   # → writes ../playground/app.js
```

Then open `playground/index.html` (any static server, or just the file). The bundle is a build
artifact (git-ignored); the sources are `js/web/app.ts` + `js/web/examples.ts` and this folder's
`index.html`.

## The `<mtph-doc>` web component

`mtph-doc.html` is a live gallery of the `<mtph-doc>` custom element — a one-tag way to embed a
`.mtph` problem in any page (figures, LaTeX, quizzes, `params:` sliders), with nothing to install
on the host page. It loads a second bundle, `playground/mtph-doc.js`:

```bash
cd js && npm run build:webcomponent   # → writes ../playground/mtph-doc.js
```

Source is `js/web/mtph-doc.ts` (the element) + `js/web/embed-core.ts` (its pure, unit-tested core).
The element renders each problem inside a sandboxed iframe fed the exact self-contained artifact
HTML, and the iframe reports its height back so it grows to fit. Both bundles are built by the Pages
workflow, so the gallery is live on the deployed site too.

## Deploy

`.github/workflows/pages.yml` builds both bundles (`build:web` + `build:webcomponent`) and publishes
this folder to GitHub Pages on every push to `main`. Enable it once under
**Settings → Pages → Source: GitHub Actions**.
