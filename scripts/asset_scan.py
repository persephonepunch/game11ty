#!/usr/bin/env python3
"""
Release scan for game11ty's assets. Gates every deploy.

    python3 scripts/asset_scan.py src                 # scan inputs, exit 1 on any error
    python3 scripts/asset_scan.py --manifest _site    # write a SHA-256 manifest of the build

CI runs the scan in a throwaway container with no network (--network none) and
no secrets, so a hostile file has nothing to reach. Standard library only.

Checks, per file:
  every file   real type (magic bytes) matches the extension
  JPG/PNG/WebP decodable container, rights XMP present (WebStatement + alt text)
  SVG          parses as XML; no script, on* handlers, javascript: links,
               foreignObject or external references
  glTF/GLB     header and chunks valid, every bufferView and accessor in bounds,
               asset.copyright set and not a tool's default claim
  PDF          no JavaScript, auto-run or launch actions
"""
import hashlib, json, re, struct, sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCANNED = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".glb", ".gltf",
           ".pdf", ".ico", ".css", ".js", ".json", ".md", ".bin", ".woff", ".woff2"}
TEXT = {".css", ".js", ".json", ".md", ".gltf"}
RASTER = {".jpg", ".jpeg", ".png", ".webp"}
# exporters that stamp their own copyright on other people's models
TOOL_COPYRIGHT = re.compile(r"\(c\)\s*Adobe Inc\.", re.I)


def sniff(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff": return "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "webp"
    if b[:6] in (b"GIF87a", b"GIF89a"): return "gif"
    if b[:4] == b"glTF": return "glb"
    if b[:5] == b"%PDF-": return "pdf"
    if b[:4] == b"\x00\x00\x01\x00": return "ico"
    if b[:4] == b"wOF2": return "woff2"
    if b[:4] == b"wOFF": return "woff"
    head = b[:512].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        return "svg" if b"<svg" in b[:4096].lower() else "xml"
    if b[:2] == b"PK": return "zip"
    if b[:2] == b"MZ": return "exe"
    if b[:4] == b"\x7fELF": return "elf"
    try:
        b[:4096].decode("utf-8"); return "text"
    except UnicodeDecodeError:
        return "binary"


EXPECT = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png", ".webp": "webp", ".gif": "gif",
          ".svg": "svg", ".glb": "glb", ".pdf": "pdf", ".ico": "ico",
          ".woff": "woff", ".woff2": "woff2", ".bin": None}


def check_type(p, b, out):
    kind = sniff(b)
    if kind in ("exe", "elf"):
        out.append(("error", f"executable content ({kind})"))
    ext = p.suffix.lower()
    want = EXPECT.get(ext, "text" if ext in TEXT else None)
    if want and kind != want:
        out.append(("error", f"extension {ext} but content is {kind}"))


def check_raster(p, b, out):
    if p.suffix.lower() == ".png":
        i = 8
        while i < len(b):
            if i + 8 > len(b):
                out.append(("error", "truncated PNG chunk")); return
            n, t = struct.unpack(">I4s", b[i:i + 8])
            if i + 12 + n > len(b):
                out.append(("error", f"PNG chunk {t!r} runs past end of file")); return
            i += 12 + n
            if t == b"IEND": break
    m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", b, re.S)
    if not m:
        out.append(("error", "no XMP packet (rights and alt text missing)")); return
    x = m.group()
    if b"WebStatement" not in x:
        out.append(("error", "XMP has no xmpRights:WebStatement"))
    if b"AltTextAccessibility" not in x:
        out.append(("warn", "XMP has no Iptc4xmpCore:AltTextAccessibility"))


SVG_BAD = [
    (re.compile(r"<\s*script", re.I), "contains <script>"),
    (re.compile(r"\son[a-z]+\s*=", re.I), "contains an on* event handler"),
    (re.compile(r"javascript:", re.I), "contains a javascript: link"),
    (re.compile(r"<\s*foreignObject", re.I), "contains <foreignObject>"),
    (re.compile(r"(?:xlink:)?href\s*=\s*[\"']\s*(?:https?:|//)", re.I), "references an external URL"),
    (re.compile(r"<!ENTITY", re.I), "declares an XML entity"),
]


def check_svg(p, b, out):
    text = b.decode("utf-8", "replace")
    for rx, why in SVG_BAD:
        if rx.search(text):
            out.append(("error", f"SVG {why}"))
    try:
        ET.fromstring(b)
    except ET.ParseError as e:
        out.append(("error", f"SVG is not well-formed XML: {e}"))


def gltf_bounds(gltf, buffers, out):
    """Every bufferView inside its buffer, every accessor inside its bufferView."""
    size = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
    comp = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    views = gltf.get("bufferViews", [])
    for i, v in enumerate(views):
        blen = buffers.get(v.get("buffer", 0))
        if blen is None:
            out.append(("error", f"bufferView {i} points at a missing buffer")); continue
        if v.get("byteOffset", 0) + v.get("byteLength", 0) > blen:
            out.append(("error", f"bufferView {i} runs past the end of its buffer"))
    for i, a in enumerate(gltf.get("accessors", [])):
        if "bufferView" not in a:
            continue  # sparse/zero accessor, or decoded by an extension (Draco)
        if a["bufferView"] >= len(views):
            out.append(("error", f"accessor {i} points at a missing bufferView")); continue
        v = views[a["bufferView"]]
        elem = size.get(a.get("type"), 0) * comp.get(a.get("componentType"), 0)
        stride = v.get("byteStride") or elem
        need = a.get("byteOffset", 0) + (stride * (a.get("count", 0) - 1) + elem if a.get("count") else 0)
        if need > v.get("byteLength", 0):
            out.append(("error", f"accessor {i} reads past the end of bufferView {a['bufferView']}"))


def check_gltf_rights(gltf, out):
    c = (gltf.get("asset") or {}).get("copyright", "")
    if not c:
        out.append(("warn", "asset.copyright is empty"))
    elif TOOL_COPYRIGHT.search(c):
        out.append(("error", f"asset.copyright is an exporter's default: {c!r}"))
    if "KHR_xmp_json_ld" not in gltf.get("extensionsUsed", []):
        out.append(("warn", "no KHR_xmp_json_ld rights packet"))


def check_glb(p, b, out):
    if len(b) < 20:
        out.append(("error", "GLB shorter than its header")); return
    magic, version, length = struct.unpack("<4sII", b[:12])
    if version != 2:
        out.append(("error", f"GLB version {version}, expected 2"))
    if length != len(b):
        out.append(("error", f"GLB header says {length} bytes, file is {len(b)}"))
    jlen, jtype = struct.unpack("<I4s", b[12:20])
    if jtype != b"JSON" or 20 + jlen > len(b):
        out.append(("error", "GLB JSON chunk missing or out of bounds")); return
    try:
        gltf = json.loads(b[20:20 + jlen])
    except ValueError as e:
        out.append(("error", f"GLB JSON is invalid: {e}")); return
    buffers, off = {}, 20 + jlen
    if off + 8 <= len(b):
        blen, btype = struct.unpack("<I4s", b[off:off + 8])
        if btype == b"BIN\x00":
            if off + 8 + blen > len(b):
                out.append(("error", "GLB BIN chunk runs past end of file"))
            buffers[0] = blen
    gltf_bounds(gltf, buffers, out)
    check_gltf_rights(gltf, out)


def check_gltf(p, b, out):
    try:
        gltf = json.loads(b)
    except ValueError as e:
        out.append(("error", f"glTF JSON is invalid: {e}")); return
    buffers = {}
    for i, buf in enumerate(gltf.get("buffers", [])):
        uri = buf.get("uri", "")
        if uri.startswith(("http:", "https:", "//")):
            out.append(("error", f"buffer {i} loads from an external URL"))
        elif ".." in Path(uri).parts or uri.startswith("/"):
            out.append(("error", f"buffer {i} path escapes the model folder"))
        elif uri and not uri.startswith("data:"):
            f = p.parent / uri
            buffers[i] = f.stat().st_size if f.exists() else None
            if buffers[i] is None:
                out.append(("error", f"buffer {i} file {uri} is missing"))
    gltf_bounds(gltf, {k: v for k, v in buffers.items() if v is not None}, out)
    check_gltf_rights(gltf, out)


PDF_BAD = [(rb"/JavaScript\b|/JS\b", "embeds JavaScript"), (rb"/OpenAction\b", "has an auto-run OpenAction"),
           (rb"/AA\b", "has additional-action triggers"), (rb"/Launch\b", "can launch programs"),
           (rb"/EmbeddedFile\b", "embeds files")]


def check_pdf(p, b, out):
    for rx, why in PDF_BAD:
        if re.search(rx, b):
            out.append(("error", f"PDF {why}"))
    if b"%%EOF" not in b[-2048:]:
        out.append(("warn", "PDF has no %%EOF trailer"))


def scan(root: Path):
    results = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SCANNED:
            continue
        b, out = p.read_bytes(), []
        check_type(p, b, out)
        ext = p.suffix.lower()
        if ext in RASTER and sniff(b) in ("jpg", "png", "webp"):
            check_raster(p, b, out)
        elif ext == ".svg":
            check_svg(p, b, out)
        elif ext == ".glb":
            check_glb(p, b, out)
        elif ext == ".gltf":
            check_gltf(p, b, out)
        elif ext == ".pdf":
            check_pdf(p, b, out)
        results[str(p.relative_to(root))] = out
    return results


def manifest(root: Path):
    files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob("*")) if p.is_file() and p.name != "asset-manifest.json"}
    (root / "asset-manifest.json").write_text(json.dumps({"algorithm": "sha256", "files": files}, indent=1) + "\n")
    print(f"asset-manifest.json: {len(files)} files hashed")


def main():
    if sys.argv[1:2] == ["--manifest"]:
        return manifest(Path(sys.argv[2]))
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    results = scan(root)
    errors = sum(1 for v in results.values() for lvl, _ in v if lvl == "error")
    warns = sum(1 for v in results.values() for lvl, _ in v if lvl == "warn")
    for f, issues in results.items():
        for lvl, msg in issues:
            print(f"{lvl.upper():5}  {f}: {msg}")
    print(f"\n{len(results)} files scanned, {errors} error(s), {warns} warning(s)")
    Path("scan-report.json").write_text(json.dumps(
        {"root": str(root), "files": len(results), "errors": errors, "warnings": warns,
         "results": {k: [{"level": l, "message": m} for l, m in v] for k, v in results.items() if v}},
        indent=1) + "\n")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
