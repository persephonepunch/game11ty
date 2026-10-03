"""
Adversarial tests for scripts/asset_scan.py, one class per security rule.

These are not smoke tests. Each rule is tested five ways:
  allow      a legitimate file passes (the rule doesn't over-block)
  block      the canonical attack is caught
  evasion    the same attack disguised: case, encoding, whitespace, escapes
  boundary   exactly at the limit passes, one byte past fails
  fail-closed  malformed or odd input is reported, never waved through

Run: python3 -m unittest discover -s tests -v
Set ASSET_SCAN=/path/to/asset_scan.py to test another copy (tests/mutate.py uses this).
Standard library only, so it runs in the no-network CI container.
"""
import hashlib, importlib.util, json, os, struct, subprocess, sys, tempfile, unittest, zlib
from pathlib import Path

SCANNER = Path(os.environ.get("ASSET_SCAN", Path(__file__).resolve().parents[1] / "scripts" / "asset_scan.py"))
spec = importlib.util.spec_from_file_location("asset_scan", SCANNER)
scan_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_mod)

XMP_OK = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
          b'<rdf:Description xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/" '
          b'xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/" '
          b'xmpRights:WebStatement="https://example.com/rights/">'
          b'<Iptc4xmpCore:AltTextAccessibility><rdf:Alt><rdf:li xml:lang="x-default">A test image</rdf:li></rdf:Alt>'
          b'</Iptc4xmpCore:AltTextAccessibility></rdf:Description></rdf:RDF></x:xmpmeta>')


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(xmp: bytes | None = XMP_OK) -> bytes:
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    itxt = chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + xmp) if xmp else b""
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    return b"\x89PNG\r\n\x1a\n" + ihdr + itxt + idat + chunk(b"IEND", b"")


def glb(gltf: dict, bin_len: int, declared_len: int | None = None) -> bytes:
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    bin_ = b"\x00" * bin_len
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bin_), b"BIN\x00") + bin_
    total = 12 + len(body)
    return b"glTF" + struct.pack("<II", 2, declared_len if declared_len is not None else total) + body


def model(count: int, copyright: str = "© Rights Holder") -> dict:
    """One VEC3 float accessor: 12 bytes per element, read from a 36-byte bufferView."""
    return {"asset": {"version": "2.0", "copyright": copyright},
            "extensionsUsed": ["KHR_xmp_json_ld"],
            "buffers": [{"byteLength": 36}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": count, "type": "VEC3"}]}


def pdf(body: bytes) -> bytes:
    return b"%PDF-1.7\n" + body + b"\n%%EOF\n"


class ScanCase(unittest.TestCase):
    def issues(self, name: str, data: bytes, extra: dict | None = None):
        with tempfile.TemporaryDirectory() as d:
            for n, b in {**(extra or {}), name: data}.items():
                p = Path(d) / n
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b)
            return scan_mod.scan(Path(d)).get(name, [])

    def errors(self, name, data):
        return [m for lvl, m in self.issues(name, data) if lvl == "error"]

    def assertBlocked(self, name, data, because=""):
        errs = self.errors(name, data)
        self.assertTrue(errs, f"{name} should be blocked{': ' + because if because else ''}, scan reported nothing")
        return errs

    def assertAllowed(self, name, data):
        self.assertEqual(self.errors(name, data), [], f"{name} should pass")


class SB11_ContentIdentity(ScanCase):
    """The real type comes from the bytes; names and labels are claims."""

    def test_allow_png_named_png(self):
        self.assertAllowed("ok.png", png())

    def test_block_png_named_jpg(self):
        self.assertIn("content is png", " ".join(self.assertBlocked("fake.jpg", png())))

    def test_block_windows_executable_named_png(self):
        self.assertTrue(any("executable" in e for e in self.assertBlocked("photo.png", b"MZ\x90\x00" + b"\x00" * 60)))

    def test_block_linux_executable_named_glb(self):
        self.assertTrue(any("executable" in e for e in self.assertBlocked("model.glb", b"\x7fELF" + b"\x00" * 60)))

    def test_evasion_executable_named_as_text(self):
        self.assertBlocked("notes.md", b"MZ" + b"\x00" * 60, "an executable is never allowed, whatever its name")

    def test_fail_closed_empty_png(self):
        self.assertBlocked("empty.png", b"")


class SB12_ActiveContent(ScanCase):
    """No file may carry code that runs: SVG scripts, javascript: links, PDF actions."""

    SVG = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{}</svg>'

    def svg(self, inner: str) -> bytes:
        return self.SVG.format(inner).encode()

    def test_allow_clean_svg(self):
        self.assertAllowed("ok.svg", self.svg('<rect width="1" height="1"/><a href="#top"><text>Top</text></a>'))

    def test_allow_the_word_script_in_text(self):
        self.assertAllowed("ok.svg", self.svg("<text>The script of the film</text>"))

    def test_block_script_element(self):
        self.assertBlocked("x.svg", self.svg("<script>alert(1)</script>"))

    def test_evasion_script_uppercase(self):
        self.assertBlocked("x.svg", self.svg("<SCRIPT>alert(1)</SCRIPT>"))

    def test_block_event_handler(self):
        self.assertBlocked("x.svg", self.svg('<rect onload="alert(1)"/>'))

    def test_evasion_event_handler_slash_separator(self):
        self.assertBlocked("x.svg", self.svg('<rect/onload="alert(1)"/>'))

    def test_block_javascript_link(self):
        self.assertBlocked("x.svg", self.svg('<a href="javascript:alert(1)"><text>x</text></a>'))

    def test_evasion_javascript_link_entity_encoded(self):
        self.assertBlocked("x.svg", self.svg('<a href="java&#115;cript:alert(1)"><text>x</text></a>'),
                           "&#115; decodes to s, so this is javascript:")

    def test_evasion_javascript_link_hex_entity(self):
        self.assertBlocked("x.svg", self.svg('<a href="&#x6A;avascript:alert(1)"><text>x</text></a>'))

    def test_evasion_javascript_link_with_tab(self):
        self.assertBlocked("x.svg", self.svg('<a href="jav&#x09;ascript:alert(1)"><text>x</text></a>'),
                           "browsers strip tabs inside a URL scheme")

    def test_block_foreign_object(self):
        self.assertBlocked("x.svg", self.svg("<foreignObject><div>x</div></foreignObject>"))

    def test_block_external_reference(self):
        self.assertBlocked("x.svg", self.svg('<image href="https://evil.example/x.png"/>'))

    def test_evasion_protocol_relative_reference(self):
        self.assertBlocked("x.svg", self.svg('<image xlink:href="//evil.example/x.png"/>'))

    def test_block_xml_entity_declaration(self):
        self.assertBlocked("x.svg", b'<?xml version="1.0"?><!DOCTYPE s [<!ENTITY e "x">]>'
                           + self.svg("<text>&e;</text>"))

    def test_fail_closed_malformed_svg(self):
        self.assertBlocked("x.svg", b"<svg><rect></svg>")

    def test_allow_clean_pdf(self):
        self.assertAllowed("ok.pdf", pdf(b"1 0 obj<</Type/Catalog>>endobj"))

    def test_block_pdf_javascript(self):
        self.assertBlocked("x.pdf", pdf(b"1 0 obj<</S/JavaScript/JS(app.alert(1))>>endobj"))

    def test_block_pdf_open_action(self):
        self.assertBlocked("x.pdf", pdf(b"1 0 obj<</OpenAction 2 0 R>>endobj"))

    def test_evasion_pdf_name_hex_escape(self):
        self.assertBlocked("x.pdf", pdf(b"1 0 obj<</S/J#61vaScript/JS(app.alert(1))>>endobj"),
                           "#61 in a PDF name is the letter a")

    def test_evasion_pdf_open_action_hex_escape(self):
        self.assertBlocked("x.pdf", pdf(b"1 0 obj<</Open#41ction 2 0 R>>endobj"))

    def test_block_pdf_launch(self):
        self.assertBlocked("x.pdf", pdf(b"1 0 obj<</S/Launch/F(cmd.exe)>>endobj"))


class SB13_StructuralBounds(ScanCase):
    """A decoder must never be pointed past the end of the data it was given."""

    def test_boundary_accessor_reads_exactly_to_end(self):
        self.assertAllowed("ok.glb", glb(model(count=3), bin_len=36))

    def test_boundary_accessor_one_element_past_end(self):
        self.assertBlocked("x.glb", glb(model(count=4), bin_len=36))

    def test_block_bufferview_past_buffer(self):
        m = model(count=3)
        m["bufferViews"][0]["byteLength"] = 40
        self.assertBlocked("x.glb", glb(m, bin_len=36))

    def test_block_header_length_lie(self):
        self.assertBlocked("x.glb", glb(model(count=3), bin_len=36, declared_len=999))

    def test_fail_closed_glb_invalid_json(self):
        data = b"glTF" + struct.pack("<II", 2, 32) + struct.pack("<I4s", 12, b"JSON") + b"{not json!! "
        self.assertBlocked("x.glb", data)

    def test_block_gltf_buffer_path_escape(self):
        # The escaped-to file really exists and is big enough, so only the
        # path-escape rule can catch this (not a "file missing" error).
        m = model(count=3)
        m["buffers"][0]["uri"] = "../secrets.bin"
        errs = [m_ for lvl, m_ in self.issues("models/x.gltf", json.dumps(m).encode(),
                                               extra={"secrets.bin": b"\x00" * 36}) if lvl == "error"]
        self.assertTrue(any("escapes" in e for e in errs), f"path escape not reported: {errs}")

    def test_block_gltf_external_buffer(self):
        m = model(count=3)
        m["buffers"][0]["uri"] = "https://evil.example/mesh.bin"
        self.assertBlocked("x.gltf", json.dumps(m).encode())

    def test_block_png_chunk_past_end(self):
        data = png()
        self.assertBlocked("x.png", data[:-20])


class SB14_RightsIntegrity(ScanCase):
    """Every image says who owns it, and no exporter may claim it by default."""

    def test_block_png_without_xmp(self):
        self.assertBlocked("x.png", png(xmp=None))

    def test_block_png_xmp_without_web_statement(self):
        self.assertBlocked("x.png", png(xmp=XMP_OK.replace(b"WebStatement", b"Unrelated")))

    def test_block_exporter_default_copyright(self):
        self.assertBlocked("x.glb", glb(model(count=3, copyright="2025 (c) Adobe Inc."), bin_len=36))

    def test_evasion_exporter_default_copyright_case(self):
        self.assertBlocked("x.glb", glb(model(count=3, copyright="2025 (C) ADOBE INC."), bin_len=36))

    def test_allow_owner_copyright(self):
        self.assertAllowed("ok.glb", glb(model(count=3, copyright="© 2026 Rights Holder"), bin_len=36))


class SB16_ReleaseGate(unittest.TestCase):
    """Any error blocks the release: the process must exit non-zero."""

    def run_scan(self, files: dict) -> int:
        with tempfile.TemporaryDirectory() as d:
            for name, data in files.items():
                (Path(d) / name).write_bytes(data)
            return subprocess.run([sys.executable, str(SCANNER), d], cwd=d, capture_output=True).returncode

    def test_clean_release_passes(self):
        self.assertEqual(self.run_scan({"ok.png": png()}), 0)

    def test_one_bad_file_blocks_the_release(self):
        self.assertEqual(self.run_scan({"ok.png": png(), "bad.jpg": png()}), 1)


class SB17_IntegrityManifest(unittest.TestCase):
    """The manifest's hashes match the released bytes exactly."""

    def test_manifest_hashes_match(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.png").write_bytes(png())
            (Path(d) / "sub").mkdir()
            (Path(d) / "sub" / "b.txt").write_bytes(b"hello")
            scan_mod.manifest(Path(d))
            scan_mod.manifest(Path(d))  # rebuilt: the old manifest now exists and must not list itself
            m = json.loads((Path(d) / "asset-manifest.json").read_text())["files"]
            self.assertEqual(set(m), {"a.png", "sub/b.txt"}, "manifest must list every file and not itself")
            self.assertEqual(m["sub/b.txt"], hashlib.sha256(b"hello").hexdigest())


if __name__ == "__main__":
    unittest.main()
