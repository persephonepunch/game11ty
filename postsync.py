#!/usr/bin/env python3
"""
Re-apply what sync.py can't know about. Run after every sync:

    python3 sync.py && python3 postsync.py

sync.py regenerates src/*.njk and the layout from Webflow, so anything added
on top of Webflow's markup lives here, driven by src/_data/images.json and
src/_data/site.json -> rights:

  - alt text from images.json onto every matching <img>
  - og:image:alt, schema.org ImageObject JSON-LD and favicon.ico in the layout
  - XMP (alt text, description, rights) written into the image files and PDFs
  - Webflow's favicons are PNGs saved under .jpg names; renamed to .png
  - favicon.ico rebuilt from the largest favicon

Idempotent: safe to run twice. Needs exiftool and Pillow.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

SRC = Path("src")
ASSETS = SRC / "assets"
images = json.loads((SRC / "_data/images.json").read_text())
rights = json.loads((SRC / "_data/site.json").read_text())["rights"]
templates = list(SRC.glob("*.njk")) + list(SRC.glob("_includes/*.njk"))

if not shutil.which("exiftool"):
    sys.exit("exiftool not found - brew install exiftool")


# --- PNGs that Webflow serves under .jpg names ---------------------------
for f in sorted(ASSETS.glob("*.jpg")):
    if f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n":
        png = f.with_suffix(".png")
        f.replace(png)
        for t in templates:
            t.write_text(t.read_text().replace(f"/assets/{f.name}", f"/assets/{png.name}"))
        print(f"  renamed {f.name} -> .png (PNG data)")


# --- alt text --------------------------------------------------------------
def attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;")

for t in SRC.glob("*.njk"):
    s = t.read_text()
    for img in images:
        s = re.sub(r'(<img\b[^>]*?\balt=")[^"]*("[^>]*?\bsrc="' + re.escape(img["src"]) + '")',
                   lambda m: m.group(1) + attr(img["alt"]) + m.group(2), s)
    og = next((i for i in images if i.get("og")), None)
    if og and f'ogImage: "{og["src"]}"' in s and "ogImageAlt:" not in s:
        s = s.replace(f'ogImage: "{og["src"]}"\n',
                      f'ogImage: "{og["src"]}"\nogImageAlt: {json.dumps(og["alt"], ensure_ascii=False)}\n', 1)
    t.write_text(s)


# --- layout: og:image:alt, JSON-LD, favicon.ico ----------------------------
base = SRC / "_includes/base.njk"
s = base.read_text()
if "postsync:head" not in s:
    s = s.replace('  <meta content="website" property="og:type"/>\n', '''  <meta content="website" property="og:type"/>
  {#- postsync:head #}
  {% if ogImageAlt %}<meta property="og:image:alt" content="{{ ogImageAlt }}"><meta name="twitter:image:alt" content="{{ ogImageAlt }}">{% endif %}
  {% if page.url == "/" %}<script type="application/ld+json">{{ {
    "@context": "https://schema.org",
    "@graph": images | imageObjects(site.url, site.rights)
  } | dump | safe }}</script>{% endif %}
  <link href="/favicon.ico" rel="icon" sizes="16x16 32x32 48x48"/>
''', 1)
    assert "postsync:head" in s, "base.njk: og:type meta not found - layout changed?"
    base.write_text(s)


# --- favicon.ico -------------------------------------------------------------
from PIL import Image
icons = sorted(ASSETS.glob("*favicon*.png"), key=lambda p: Image.open(p).width)
if icons:
    Image.open(icons[-1]).save(SRC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


# --- XMP ---------------------------------------------------------------------
RIGHTS = [
    "-overwrite_original", "-m", "-q",
    "-MWG:Copyright=" + rights["notice"],
    "-MWG:Creator=" + rights["holder"],
    "-XMP-xmpRights:Marked=True",
    "-XMP-xmpRights:UsageTerms=" + rights["terms"],
    "-XMP-xmpRights:WebStatement=" + rights["url"],
    "-XMP-plus:LicensorURL=" + rights["url"],
    "-XMP-photoshop:Credit=Respective rights holders (demo)",
]

def xmp(path, title, alt):
    subprocess.run(["exiftool", *RIGHTS, "-XMP-dc:Title=" + title, "-MWG:Description=" + alt,
                    "-XMP-iptcCore:AltTextAccessibility=" + alt, str(path)], check=True)

n = 0
for img in images:
    f = SRC / img["src"].lstrip("/")
    if f.suffix.lower() in (".jpg", ".jpeg", ".png") and f.exists():
        xmp(f, img["title"], img["alt"]); n += 1
for f in icons:
    xmp(f, "Site icon", "Close-up of red-lit cooling fans inside a gaming desktop"); n += 1
for f in SRC.glob("docs/*.pdf"):  # title/description were set by hand; rights only
    subprocess.run(["exiftool", *RIGHTS, str(f)], check=True); n += 1
print(f"  XMP written to {n} file(s); alt text applied from images.json")
