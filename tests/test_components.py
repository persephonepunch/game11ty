"""Components from the repo: sync.py swaps marked Webflow elements for includes.

    python3 -m unittest tests/test_components.py

Needs beautifulsoup4 + requests (sync.py imports them). The CI scan container
has neither, so these skip there; run them where you run sync.py.
"""
import json, re, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from bs4 import BeautifulSoup
    sys.path.insert(0, str(ROOT))
    import sync
except ImportError:  # pragma: no cover
    sync = None


def make(out, have=("video", "account"), by_class=None, prefix="component-"):
    comp = Path(out) / "src/_includes/components"
    comp.mkdir(parents=True, exist_ok=True)
    for n in have:
        (comp / f"{n}.njk").write_text("x")
    cfg = sync.load_config("/nonexistent")
    cfg.update(site="https://example.webflow.io/", out=str(out),
               components={"byClass": dict(by_class or {}), "classPrefix": prefix})
    return sync.Sync(cfg)


def run(html, **kw):
    with tempfile.TemporaryDirectory() as d:
        s = make(d, **kw)
        soup = BeautifulSoup(f"<body>{html}</body>", "html.parser")
        s.components_in(soup.body)
        return s.place_components(str(soup.body)), s


def props(out):
    return [json.loads(x.split(" %}")[0]) for x in out.split("{% set props = ")[1:]]


@unittest.skipIf(sync is None, "beautifulsoup4/requests not installed")
class Matching(unittest.TestCase):
    def test_data_component(self):
        out, s = run('<div data-component="video" data-id="abc"></div>')
        self.assertIn('{% include "components/video.njk" %}', out)
        self.assertEqual(props(out), [{"id": "abc"}])

    def test_by_class_drops_the_matched_class_only(self):
        out, _ = run('<div class="yt-lead is-dark" data-id="x">Watch</div>',
                     by_class={"yt-lead": "video"})
        self.assertIn("components/video.njk", out)
        self.assertNotIn("yt-lead", out)
        self.assertEqual(props(out), [{"id": "x", "classes": "is-dark", "text": "Watch"}])

    def test_prefix_convention(self):
        out, _ = run('<section class="hero component-video"></section>')
        self.assertIn("components/video.njk", out)
        self.assertEqual(props(out), [{"classes": "hero"}])

    def test_prefix_matches_whole_class_names_only(self):
        out, s = run('<div class="x-component-video"></div><div class="components-list"></div>')
        self.assertNotIn("include", out)
        self.assertEqual(s.unknown, {})

    def test_prefix_off(self):
        out, s = run('<div class="component-video"></div>', prefix="")
        self.assertNotIn("include", out)
        self.assertEqual(s.unknown, {})

    def test_unknown_is_reported_and_left_as_drawn(self):
        out, s = run('<div class="component-nope">keep</div>')
        self.assertEqual(s.unknown, {"nope": 1})
        self.assertIn('class="component-nope"', out)

    def test_data_component_wins_over_class(self):
        out, s = run('<div data-component="video" class="component-account"></div>')
        self.assertIn("components/video.njk", out)
        self.assertEqual(s.placed, {"video": 1})

    def test_nested_goes_with_parent(self):
        out, s = run('<div class="component-account"><div class="component-video"></div></div>')
        self.assertEqual(out.count("{% include"), 1)
        self.assertEqual(s.placed, {"account": 1})

    def test_text_is_text_not_html(self):
        out, _ = run('<a class="component-account btn" href="#">Sign  <b>in</b></a>')
        self.assertEqual(props(out), [{"classes": "btn", "text": "Sign in"}])

    def test_same_component_same_marker(self):
        with tempfile.TemporaryDirectory() as d:
            s = make(d)
            a = BeautifulSoup('<body><div class="component-video"></div></body>', "html.parser")
            b = BeautifulSoup('<body><div class="component-video"></div></body>', "html.parser")
            s.components_in(a.body); s.components_in(b.body)
            self.assertEqual(str(a), str(b))


@unittest.skipIf(sync is None, "beautifulsoup4/requests not installed")
class EndToEnd(unittest.TestCase):
    """write() on two in-memory pages: chrome still splits, includes survive njk_escape."""

    def page(self, main, current):
        cur = lambda p: ' class="nav-link w--current"' if p == current else ' class="nav-link"'
        return BeautifulSoup(
            '<html data-wf-page="p1"><head><title>T</title></head><body>'
            f'<nav class="navbar"><a{cur("/")} href="/">Home</a><a{cur("/about")} href="/about">About</a>'
            '<div class="component-account nav-right">Sign in</div></nav>'
            f'<main>{main}</main>'
            '<footer class="footer"><a href="/terms">Terms</a></footer>'
            '</body></html>', "html.parser")

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            s = make(d)
            s.pages = [("/", self.page('<h1>Home</h1><div data-component="video" data-id="v1"></div>', "/")),
                       ("/about", self.page("<h1>{{ not ours }}</h1>", "/about"))]
            s.transform()
            s.write()
            src = Path(d) / "src"
            header = (src / "_includes/header.njk").read_text()
            index = (src / "index.njk").read_text()
            about = (src / "about.njk").read_text()

            self.assertIn('class="navbar"', header, "nav still recognised as shared chrome")
            self.assertIn('{% include "components/account.njk" %}', header)
            self.assertIn('"classes": "nav-right"', header)
            self.assertNotIn("navbar", index)
            self.assertIn('{% set props = {"id": "v1"} %}{% include "components/video.njk" %}', index)
            self.assertIn('{{ "{{" }} not ours }}', about, "Webflow braces still escaped")
            self.assertNotRegex(header + index + about, r"@@WFCOMPONENT")
            self.assertTrue((src / "_includes/components/video.njk").exists(),
                            "the sync never touches the repo's components")


if __name__ == "__main__":
    unittest.main()
