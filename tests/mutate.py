#!/usr/bin/env python3
"""
Mutation check: proves the tests have teeth.

A smoke test passes whether or not a rule works. This script breaks one rule at
a time in a throwaway copy of asset_scan.py and runs the test suite against it.
Every mutant must be "killed" (at least one test fails). A mutant that survives
means a rule could be deleted without any test noticing: write the missing test.

    python3 tests/mutate.py
"""
import os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts" / "asset_scan.py").read_text()

# (rule, what the mutant breaks, exact text, replacement)
MUTANTS = [
    ("SB-11", "executables allowed", 'if kind in ("exe", "elf"):', "if False:"),
    ("SB-11", "extension never compared to content", "if want and kind != want:", "if False:"),
    ("SB-11", "unlisted types skipped instead of blocked", 'results[str(p.relative_to(root))] = [("error", f"type {p.suffix or \'(no extension)\'} is not on the allow list")]', "pass"),
    ("SB-11", "PNG signature not recognised", 'if b[:8] == b"\\x89PNG\\r\\n\\x1a\\n": return "png"', "pass"),
    ("SB-12", "SVG <script> rule removed", '(re.compile(r"<\\s*script", re.I), "contains <script>"),', ""),
    ("SB-12", "SVG event-handler rule removed", '(re.compile(r"\\son[a-z]+\\s*=", re.I), "contains an on* event handler"),', ""),
    ("SB-12", "SVG character references not decoded", "html.unescape(text)", "text"),
    ("SB-12", "PDF #xx name escapes not normalised", "lambda m: bytes([int(m.group(1), 16)])", "lambda m: m.group(0)"),
    ("SB-12", "PDF OpenAction rule removed", '(rb"/OpenAction\\b", "has an auto-run OpenAction"),', ""),
    ("SB-13", "accessor bounds off by one element", 'if need > v.get("byteLength", 0):', 'if need > v.get("byteLength", 0) + 12:'),
    ("SB-13", "GLB header length not checked", "if length != len(b):", "if False:"),
    ("SB-13", "glTF buffer path escape allowed", 'elif ".." in Path(uri).parts or uri.startswith("/"):', "elif False:"),
    ("SB-14", "XMP WebStatement not required", 'if b"WebStatement" not in x:', "if False:"),
    ("SB-14", "exporter copyright match is case-sensitive", 'Adobe Inc\\.", re.I)', 'Adobe Inc\\.")'),
    ("SB-16", "release not blocked on errors", "sys.exit(1 if errors else 0)", "sys.exit(0)"),
    ("SB-17", "manifest lists itself", ' and p.name != "asset-manifest.json"', ""),
]


def main():
    survivors = 0
    for rule, what, old, new in MUTANTS:
        if old not in SOURCE:
            print(f"STALE   {rule}  {what}: mutation target not found, update tests/mutate.py")
            survivors += 1
            continue
        with tempfile.TemporaryDirectory() as d:
            mutant = Path(d) / "asset_scan.py"
            mutant.write_text(SOURCE.replace(old, new, 1))
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests")],
                               env={**os.environ, "ASSET_SCAN": str(mutant)}, capture_output=True, text=True)
        killed = r.returncode != 0
        survivors += not killed
        print(f"{'killed ' if killed else 'SURVIVED'} {rule}  {what}")
    print(f"\n{len(MUTANTS) - survivors}/{len(MUTANTS)} mutants killed")
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
