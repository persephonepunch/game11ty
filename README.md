# webflow -> 11ty

`sync.py` crawls a published Webflow site and writes an Eleventy source tree.
Replaces the Next.js `design-sync` approach (which re-scraped Webflow on every
build) with a one-shot sync, so the build no longer depends on Webflow's uptime.

Swap sites by editing one line in `config.py`, same as `design-sync/config.js`:

    config = {"site": "https://techblog-ysl.webflow.io/", ...}

Then:

    python3 -m venv .venv && .venv/bin/pip install beautifulsoup4 requests lxml
    .venv/bin/python sync.py
    .venv/bin/python postsync.py   # re-applies alt text, XMP, JSON-LD, favicon.ico
    npm install && npm run build

`--site` / `--out` / `--limit` / `--hoist-partial-scripts` override the file for
a one-off run. Re-running is idempotent: templates are regenerated, `src/assets/`
is a cache, and assets no longer referenced are pruned.

## What it does

- BFS crawl from `/`, seeded by `config["pages"]` (falls back to link-crawling
  when `sitemap.xml` 404s - which it does on all three OMEN/HP sites)
- Downloads every Webflow CDN asset to `src/assets/`, rewrites all references.
  Webflow hosts custom code under percent-encoded paths, so names are decoded
  and then sanitized back to URL-safe
- Extracts the nav/footer shared by all pages into `_includes/header.njk` /
  `footer.njk`, normalizing Webflow's `w--current` active marker away and
  re-deriving it in Nunjucks from `page.url`. Skipped for single-page sites,
  where every node is trivially "common"
- Hoists the Webflow runtime (jQuery + IX2 chunks) into the layout
- Escapes Webflow Ecommerce's own `{{wf ...}}` syntax so Nunjucks doesn't
  try to parse it
- Swaps elements marked in Webflow for components the repo owns (see below)
- Per-page `<title>` / meta -> front matter; everything else -> `base.njk`
- Warns about references broken on Webflow itself

## Components from the repo

The Next 13 design-sync `replace()` hook, as a rule instead of code. Mark an
element in Webflow and the sync swaps it for `src/_includes/components/<name>.njk`:

- `data-component="video"` (Element settings -> Custom attributes)
- a designer class mapped in `config.py` -> `components.byClass`
- the class convention `component-video`

The component gets `props`: the element's `data-*` attributes
(`data-market` -> `props.market`), its other classes (`props.classes`) and its
visible text (`props.text`). A name with no `.njk` file is reported and left as
Webflow drew it. Components in the nav/footer are placed too, inside
`header.njk` / `footer.njk`. `src/_includes/components/` is yours: the sync
reads it and never rewrites it.

## config.py

Mirrors `design-sync/config.js`. `clientRouting`, `revalidate`, `optimizeImages`
and `minifyJs` no longer apply; sync.py says so if you set them.

`hoistPartialScripts` is the one to think about per site:

- **techblog: True.** The `.fs-menu-toggle` handler was on 6 of 10 pages, so the
  mobile menu was dead on the other 4. Hoisting fixes it.
- **omenphase1: False.** Its odd-page-out scripts are genuinely page-specific
  (form handlers, scroll lock). Hoisting would run them everywhere.

Read the `! trailing scripts missing from some pages` warning before deciding.

## Before deploying

Set `src/_data/site.json` -> `url` (used to make og:image absolute).

## postsync.py

sync.py regenerates the templates from Webflow, so the additions on top live
in `postsync.py`, driven by `src/_data/images.json` (alt text per image) and
`site.json` -> `rights`. Run it after every sync. Edit alt text in
images.json, not in the templates. Needs `exiftool` and Pillow.

## Release scan

`scripts/asset_scan.py` gates every deploy. CI runs it in a container with no
network and no secrets, and the build only starts if it passes:

- every file: real type (magic bytes) matches the extension; no executables
- JPG/PNG/WebP: valid container, rights XMP (WebStatement, alt text) present
- SVG: well-formed; no script, on* handlers, javascript: links,
  foreignObject or external references
- glTF/GLB: header, chunks, bufferViews and accessors in bounds;
  `asset.copyright` set and not an exporter's default
- PDF: no JavaScript, auto-run or launch actions

Run it locally with `python3 scripts/asset_scan.py src`. The deployed site
also carries `asset-manifest.json`, a SHA-256 hash of every published file.
