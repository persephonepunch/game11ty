#!/usr/bin/env python3
"""
design-sync, in Python -> Eleventy.

Port of design-sync/helpers/bootstrap.js + fetch-webflow-page.js (cheerio),
except it emits a real 11ty source tree instead of feeding HTML strings into
React at build time. Run once; the output no longer depends on Webflow.

  crawl -> parse (BeautifulSoup) -> split shell from content -> write src/
"""
import argparse, hashlib, json, re, shutil, sys
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote

import requests
from bs4 import BeautifulSoup

ASSET_DOMAINS = {
    "assets.website-files.com", "assets-global.website-files.com",
    "cdn.prod.website-files.com", "uploads-ssl.webflow.com",
    "global-uploads.webflow.com",
}
# Per-page <head> tags become front matter; everything else is shared chrome.
PER_PAGE_META = {
    "description": "description", "og:title": "ogTitle",
    "og:description": "ogDescription", "og:image": "ogImage",
    "twitter:title": "twitterTitle", "twitter:description": "twitterDescription",
    "twitter:image": "twitterImage",
}


def njk_escape(html):
    """Neutralize template delimiters that came from Webflow.

    Webflow Ecommerce injects its own `{{wf {...} }}` syntax into the currency
    settings script, and Nunjucks tries to parse it. Emit the literal braces
    instead. Must run BEFORE we inject our own template code.
    """
    return html.replace("{{", '{{ "{{" }}').replace("{%", '{{ "{%" }}')


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


class Sync:
    def __init__(self, cfg):
        self.cfg = cfg
        self.site = cfg["site"].rstrip("/")
        self.host = urlparse(self.site).netloc
        self.out = Path(cfg["out"])
        self.limit = cfg["staticPageLimit"]
        self.hoist_partial = cfg["hoistPartialScripts"]
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "design-sync-py/1.0"
        self.assets = {}
        self.taken = {}
        self.pages = []          # [(path, soup)]

    # ---------------- fetch ----------------
    def get(self, url, quiet=False):
        try:
            r = self.s.get(url, timeout=20)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if not quiet:
                print(f"  ! {url}: {e}", file=sys.stderr)
            return None

    def internal_path(self, href, base="/"):
        href, _ = urldefrag(href.strip())
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            return None
        u = urlparse(urljoin(self.site + base, href))
        if u.netloc != self.host or Path(u.path).suffix not in ("", ".html"):
            return None
        return u.path or "/"

    def crawl(self):
        queue, seen = deque(["/"]), {"/"}
        seeds = [urlparse(u).path or "/" if "//" in u else u
                 for u in self.cfg.get("pages", [])]
        for p in seeds + self.sitemap_paths():
            if p not in seen:
                seen.add(p); queue.append(p)
        while queue and len(self.pages) < self.limit:
            path = queue.popleft()
            r = self.get(self.site + path)
            if r is None:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            self.pages.append((path, soup))
            print(f"  [{len(self.pages):>3}] {path}")
            for a in soup.select("a[href]"):
                nxt = self.internal_path(a["href"], path)
                if nxt and nxt not in seen:
                    seen.add(nxt); queue.append(nxt)

    def sitemap_paths(self):
        r = self.get(f"{self.site}/sitemap.xml", quiet=True)
        if r is None:
            print("  (no sitemap.xml - crawling links instead)")
            return []
        return [urlparse(m).path for m in re.findall(r"<loc>(.*?)</loc>", r.text)]

    # ---------------- rewrite ----------------
    def localize(self, value):
        out = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            url, _, desc = part.partition(" ")
            if url.startswith("//"):
                url = "https:" + url
            u = urlparse(urljoin(self.site, url))
            # Webflow hosts custom code under percent-encoded paths, e.g.
            # /<site>%2F<folder>%2Fkbsearchloader-1.0.0.js - decode before
            # deriving a filename or the whole path becomes the basename.
            decoded = Path(unquote(u.path))
            has_file = bool(decoded.name) and bool(decoded.suffix)
            if has_file and (u.netloc in ASSET_DOMAINS or u.netloc == self.host):
                remote = u._replace(query="", fragment="").geturl()
                local = self.asset_name(remote, decoded.name)
                url = local
            out.append(f"{url} {desc}".strip())
        return ", ".join(out)

    @staticmethod
    def safe_name(name):
        """Decoded names are readable but may contain spaces or other
        characters that are invalid unencoded in a URL. Sanitize them."""
        stem, suffix = Path(name).stem, Path(name).suffix
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "asset"
        suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix)
        return stem + suffix

    def asset_name(self, remote, name):
        """Map a remote asset to /assets/<name>, disambiguating collisions."""
        if remote in self.assets:
            return self.assets[remote]
        name = self.safe_name(name)
        local = f"/assets/{name}"
        if local in self.taken and self.taken[local] != remote:
            stem, suffix = Path(name).stem, Path(name).suffix
            digest = hashlib.sha1(remote.encode()).hexdigest()[:8]
            local = f"/assets/{stem}-{digest}{suffix}"
        self.taken[local] = remote
        self.assets[remote] = local
        return local

    def transform(self):
        for path, soup in self.pages:
            for attr in ("data-wf-domain", "data-wf-status"):
                if soup.html and soup.html.has_attr(attr):
                    del soup.html[attr]
            if self.cfg["removeBranding"]:
                for el in soup.select(".w-webflow-badge"):
                    el.decompose()

            # Nothing loads from the Webflow CDN any more, so its preconnect
            # hint is now just a wasted DNS/TLS handshake.
            for el in soup.select('link[rel~="preconnect"], link[rel~="dns-prefetch"]'):
                if urlparse(el.get("href", "")).netloc in ASSET_DOMAINS:
                    el.decompose()
            for tag, attr in (("img", "src"), ("img", "srcset"), ("source", "srcset"),
                              ("script", "src"), ("link", "href"), ("video", "poster")):
                for el in soup.find_all(tag):
                    if el.has_attr(attr):
                        el[attr] = self.localize(el[attr])

            # Lottie players carry their JSON in data-src.
            for el in soup.select("[data-src]"):
                el["data-src"] = self.localize(el["data-src"])

            # Links to files on the Webflow CDN (PDFs, downloads) are assets too.
            for a in soup.select("a[href]"):
                u = urlparse(urljoin(self.site, a["href"]))
                if u.netloc in ASSET_DOMAINS and Path(u.path).suffix:
                    a["href"] = self.localize(a["href"])
            for a in soup.select("a[href]"):
                p = self.internal_path(a["href"], path)
                if p:
                    a["href"] = p
                elif urlparse(a["href"]).scheme in ("http", "https"):
                    a["rel"] = "noopener noreferrer"
            for img in soup.select("img:not([loading])"):
                img["loading"] = "lazy"

            self.uninstall_apps(soup)

    def uninstall_apps(self, soup):
        """Strip the copy of an app that Webflow bakes into page custom code.

        The app is installed once into the layout instead, so a re-sync can
        never reintroduce a stale inline version alongside the component.
        """
        for app in self.cfg.get("apps", []):
            for sel in app.get("remove", []):
                for el in soup.select(sel):
                    el.decompose()
            tokens = app.get("removeInline", [])
            if not tokens:
                continue
            for el in soup.find_all(["script", "style"]):
                if el.get("src"):
                    continue
                text = el.get_text()
                if any(t in text for t in tokens):
                    el.decompose()

    # ---------------- shell / content split ----------------
    @staticmethod
    def normalize(node):
        """Serialize a node for cross-page comparison.

        Webflow marks the current page's nav link with `w--current` /
        `aria-current`, so an otherwise identical nav differs on every page.
        Strip those before comparing or the shared chrome never matches.
        """
        html = str(node)
        html = re.sub(r'\s*aria-current="page"', "", html)
        html = re.sub(r'\s*\bw--current\b', "", html)
        return html

    def split_shell(self):
        """Find the header/footer shared by every page.

        Webflow emits an identical nav and footer on each page, so the longest
        common prefix and suffix of the body's top-level children IS the layout.
        Whatever is left in the middle is that page's content.
        """
        bodies = [[(self.normalize(c), c) for c in soup.body.find_all(recursive=False)]
                  for _, soup in self.pages]
        if not bodies:
            return [], [], []

        # Shared chrome is only meaningful across two or more pages. With one
        # page, every node is trivially "common" and the whole body would be
        # hoisted into header.njk, leaving the page empty.
        if len(bodies) < 2:
            return [], [], [[n for _, n in bodies[0]]]

        def common(seqs, reverse=False):
            idx = 0
            while True:
                vals = set()
                for s in seqs:
                    if idx >= len(s):
                        return idx
                    vals.add(s[-1 - idx][0] if reverse else s[idx][0])
                if len(vals) != 1:
                    return idx
                idx += 1

        head_n = common(bodies)
        foot_n = common(bodies, reverse=True)
        # Never let prefix+suffix swallow a whole page.
        shortest = min(len(b) for b in bodies)
        if head_n + foot_n > shortest - 1:
            foot_n = max(0, shortest - 1 - head_n)

        header = [n for _, n in bodies[0][:head_n]]
        footer = [n for _, n in bodies[0][len(bodies[0]) - foot_n:]] if foot_n else []
        contents = [[n for _, n in (b[head_n:len(b) - foot_n] if foot_n else b[head_n:])]
                    for b in bodies]

        # Webflow's runtime (jQuery + webflow.js + IX2 chunks) sits at the end of
        # every <body>. Common-suffix matching misses it when a page also has its
        # own inline script after it, so hoist trailing scripts by identity.
        def key(node):
            src = node.get("src")
            return src.split("?")[0] if src else "inline:" + node.get_text().strip()

        trailing = []
        for c in contents:
            run = []
            while c and c[-1].name == "script":
                run.insert(0, c.pop())
            trailing.append(run)

        counts = {}
        for run in trailing:
            for k in {key(n) for n in run}:
                counts[k] = counts.get(k, 0) + 1

        total = len(contents)
        partial = {k: v for k, v in counts.items() if v < total}
        hoist_keys = set(counts) if self.hoist_partial else {
            k for k, v in counts.items() if v == total}

        # Collect across every page, not just the first - a script can be
        # missing from page 0 and still belong in the shared footer.
        seen, hoisted = set(), []
        for run in trailing:
            for n in run:
                k = key(n)
                if k in hoist_keys and k not in seen:
                    seen.add(k); hoisted.append(n)
        footer = hoisted + footer

        # Put page-specific scripts back where they were.
        for c, run in zip(contents, trailing):
            c.extend(n for n in run if key(n) not in hoist_keys)

        if partial:
            verb = "hoisted anyway" if self.hoist_partial else "left in-page"
            print(f"\n  ! trailing scripts missing from some pages ({verb}):")
            for k, v in partial.items():
                print(f"      {v}/{total} pages: {k[:90]}")

        return header, footer, contents

    def install_apps(self):
        """Emit each app's element plus its module, once, in the layout."""
        lines = []
        for app in self.cfg.get("apps", []):
            if app.get("element"):
                lines.append(app["element"])
            if app.get("module"):
                lines.append(f'<script type="module" src="{app["module"]}"></script>')
        return lines

    # ---------------- emit ----------------
    def write(self):
        src = self.out / "src"
        inc = src / "_includes"
        inc.mkdir(parents=True, exist_ok=True)

        header, footer, contents = self.split_shell()
        _, first = self.pages[0]

        # --- head: shared tags in the layout, per-page tags in front matter ---
        shared_head, page_meta = [], []
        for el in first.head.find_all(recursive=False):
            if el.name == "title" or (el.name == "meta" and el.has_attr("charset")):
                continue
            key = el.get("name") or el.get("property")
            if el.name == "meta" and key in PER_PAGE_META:
                continue
            shared_head.append(njk_escape(str(el)))

        html_attrs = njk_escape(" ".join(
            f'{k}="{v}"' for k, v in (first.html.attrs or {}).items()
            if k != "data-wf-page"
        ))
        body_attrs = njk_escape(" ".join(
            f'{k}="{" ".join(v) if isinstance(v, list) else v}"'
            for k, v in (first.body.attrs or {}).items()
        ))

        # Webflow's active-nav class is baked per page; re-derive it in 11ty
        # so the shared nav can live in one include.
        def templatize(nodes):
            html = njk_escape("\n".join(str(n) for n in nodes))
            html = re.sub(r'\s*aria-current="page"', "", html)
            html = re.sub(r'\s*\bw--current\b', "", html)

            def active(m):
                cls, href = m.group("cls"), m.group("href")
                if not href.startswith("/"):
                    return m.group(0)
                url = href if href.endswith("/") else href + "/"
                cond = "{% if page.url == '" + url + "' %} w--current{% endif %}"
                return m.group(0).replace(f'class="{cls}"', f'class="{cls}{cond}"')

            return re.sub(
                r'<a\b[^>]*class="(?P<cls>[^"]*)"[^>]*href="(?P<href>[^"]*)"[^>]*>',
                active, html)

        if self.cfg["optimizeJsLoading"]:
            for n in footer:
                if n.name != "script":
                    continue
                if n.get("src"):
                    n["defer"] = None          # deferred scripts keep source order
                elif n.string:
                    # An inline script ignores `defer`, so it would run BEFORE the
                    # deferred jQuery it depends on. Delay it to DOMContentLoaded,
                    # which fires after deferred scripts have executed.
                    n.string = ("document.addEventListener('DOMContentLoaded',"
                                "function(){" + n.string.strip() + "});")

        (inc / "header.njk").write_text(templatize(header) + "\n", encoding="utf-8")
        (inc / "footer.njk").write_text(templatize(footer) + "\n", encoding="utf-8")

        layout = ["<!DOCTYPE html>",
                  f'<html {html_attrs} data-wf-page="{{{{ wfPage }}}}">',
                  "<head>",
                  '  <meta charset="utf-8">',
                  "  <title>{{ title }}</title>",
                  '  {% if description %}<meta name="description" content="{{ description }}">{% endif %}',
                  '  {% if ogTitle or title %}<meta property="og:title" content="{{ ogTitle or title }}">{% endif %}',
                  '  {% if ogDescription or description %}<meta property="og:description" content="{{ ogDescription or description }}">{% endif %}',
                  '  {% if ogImage %}<meta property="og:image" content="'
                  '{% if ogImageRelative %}{{ site.url }}{% endif %}{{ ogImage }}">{% endif %}',
                  *(f"  {t}" for t in shared_head),
                  "</head>",
                  f"<body {body_attrs}>",
                  '{% include "header.njk" %}',
                  "",
                  "{{ content | safe }}",
                  "",
                  '{% include "footer.njk" %}',
                  *self.install_apps(),
                  "</body>", "</html>", ""]
        (inc / "base.njk").write_text("\n".join(layout), encoding="utf-8")

        # --- one file per page ---
        for (path, soup), content in zip(self.pages, contents):
            fm = {"layout": "base.njk",
                  "permalink": path if path.endswith("/") else path + "/",
                  "title": soup.title.get_text(strip=True) if soup.title else "",
                  "wfPage": soup.html.get("data-wf-page", "")}
            for el in soup.head.find_all("meta"):
                key = el.get("name") or el.get("property")
                if key in PER_PAGE_META and el.get("content"):
                    val = el["content"]
                    if key.endswith("image"):
                        val = self.localize(val)
                        # Only a local path needs site.url prefixed; an image
                        # served from elsewhere is already absolute.
                        fm["ogImageRelative"] = val.startswith("/")
                    fm.setdefault(PER_PAGE_META[key], val)

            body = njk_escape("\n".join(str(n) for n in content))
            def yaml(k, v):
                # Booleans must stay unquoted - "False" is a truthy string.
                return f"{k}: {str(v).lower()}" if isinstance(v, bool) \
                    else f'{k}: "{esc(v)}"'

            front = "\n".join(yaml(k, v) for k, v in fm.items()
                               if isinstance(v, bool) or v != "")
            name = "index" if path == "/" else path.strip("/").replace("/", "-")
            (src / f"{name}.njk").write_text(
                f"---\n{front}\n---\n\n{body}\n", encoding="utf-8")

        # --- assets ---
        adir = src / "assets"
        adir.mkdir(exist_ok=True)
        failed = []
        print(f"\nDownloading {len(self.assets)} assets...")
        for url, local in self.assets.items():
            dest = self.out / "src" / local.lstrip("/")
            if dest.exists():
                continue
            r = self.get(url, quiet=True)
            if r is None:
                failed.append((url, local))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)

        adir = self.out / "src" / "assets"
        keep = {Path(v).name for v in self.assets.values()}
        orphans = [f for f in adir.iterdir() if f.is_file() and f.name not in keep]
        for f in orphans:
            f.unlink()
        if orphans:
            print(f"  pruned {len(orphans)} asset(s) no longer referenced")

        if failed:
            print(f"\n  ! {len(failed)} asset(s) 404 on Webflow itself - "
                  f"the reference is broken upstream, not by this sync:")
            for url, local in failed:
                print(f"      {local}  <-  {url}")

        # --- project scaffold ---
        def seed(path, content):
            """Write once. These are yours to edit; a re-sync must not
            clobber a configured site URL or a renamed package."""
            if not Path(path).exists():
                Path(path).write_text(content, encoding="utf-8")

        (src / "_data").mkdir(exist_ok=True)
        seed(src / "_data" / "site.json",
             json.dumps({"url": "https://example.com", "source": self.site},
                        indent=2) + "\n")
        seed(self.out / "eleventy.config.js", 
            'export default function (eleventyConfig) {\n'
            '  eleventyConfig.addPassthroughCopy("src/assets")\n'
            '  eleventyConfig.addPassthroughCopy("src/apps")\n'
            '  return { dir: { input: "src", includes: "_includes", output: "_site" } }\n'
            '}\n')
        seed(self.out / "package.json", json.dumps({
            "name": Path(self.out).resolve().name, "private": True,
            "type": "module",
            "scripts": {"dev": "eleventy --serve", "build": "eleventy"},
            "devDependencies": {"@11ty/eleventy": "^3.1.2"},
        }, indent=2) + "\n")
        (self.out / "manifest.json").write_text(json.dumps(
            {"site": self.site, "pages": [p for p, _ in self.pages],
             "assets": self.assets}, indent=2), encoding="utf-8")


DEAD_KEYS = {
    "clientRouting": "next/link - 11ty emits plain <a> tags",
    "revalidate": "Next ISR - nothing is fetched at request time now",
    "optimizeImages": "next/image - Webflow's own srcset derivatives are kept",
    "minifyJs": "UglifyJS pass - not implemented",
}


def load_config(path):
    """Read config.py the way design-sync read config.js."""
    defaults = {"site": None, "out": ".", "pages": [], "staticPageLimit": 200,
                "removeBranding": True, "optimizeJsLoading": True,
                "hoistPartialScripts": True}
    cfg = dict(defaults)
    f = Path(path)
    if f.exists():
        ns = {}
        exec(compile(f.read_text(), str(f), "exec"), ns)
        user = ns.get("config", {})
        for k, v in user.items():
            if k in DEAD_KEYS:
                print(f"  note: `{k}` has no effect - {DEAD_KEYS[k]}")
            else:
                cfg[k] = v
    return cfg


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Sync a published Webflow site into an 11ty source tree.")
    ap.add_argument("--config", default="config.py")
    ap.add_argument("--site", help="override config['site']")
    ap.add_argument("--out", help="override config['out']")
    ap.add_argument("--limit", type=int, help="override config['staticPageLimit']")
    ap.add_argument("--hoist-partial-scripts", action="store_true", default=None,
                    help="override config['hoistPartialScripts']")
    a = ap.parse_args()

    cfg = load_config(a.config)
    if a.site:  cfg["site"] = a.site
    if a.out:   cfg["out"] = a.out
    if a.limit: cfg["staticPageLimit"] = a.limit
    if a.hoist_partial_scripts is not None:
        cfg["hoistPartialScripts"] = a.hoist_partial_scripts

    if not cfg["site"]:
        sys.exit("No site configured. Set `site` in config.py or pass --site.")

    # Idempotent: wipe generated templates, keep the asset cache.
    out = Path(cfg["out"])
    for stale in list(out.glob("src/*.njk")) + list(out.glob("src/_includes/*.njk")):
        stale.unlink()

    s = Sync(cfg)
    print(f"Crawling {s.site} ...")
    s.crawl()
    s.transform()
    s.write()
    print(f"\n{len(s.pages)} pages, {len(s.assets)} assets -> {cfg['out']}/")
