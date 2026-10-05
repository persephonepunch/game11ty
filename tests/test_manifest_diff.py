"""
Tests for scripts/manifest_diff.py (SB-24): the release diff reports every
difference in bytes, records it, and never blocks.

Run: python3 -m unittest discover -s tests -v
Set MANIFEST_DIFF=/path/to/manifest_diff.py to test another copy (tests/mutate.py uses this).
"""
import hashlib, importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(os.environ.get("MANIFEST_DIFF", Path(__file__).resolve().parents[1] / "scripts" / "manifest_diff.py"))
spec = importlib.util.spec_from_file_location("manifest_diff", SCRIPT)
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

h = lambda b: hashlib.sha256(b).hexdigest()


class SB24_ReleaseDiff(unittest.TestCase):
    def run_diff(self, previous, new, raw_previous=None):
        with tempfile.TemporaryDirectory() as d:
            p, n = Path(d) / "prev.json", Path(d) / "new.json"
            if raw_previous is not None:
                p.write_text(raw_previous)
            elif previous is not None:
                p.write_text(json.dumps({"algorithm": "sha256", "files": previous}))
            n.write_text(json.dumps({"algorithm": "sha256", "files": new}))
            return md.diff(str(p), str(n))

    def test_allow_identical_releases_report_nothing(self):
        files = {"a.png": h(b"a"), "b.css": h(b"b")}
        r = self.run_diff(files, files)
        self.assertEqual((r["added"], r["removed"], r["changed"], r["unchanged"]), ([], [], [], 2))

    def test_block_same_path_different_bytes_is_changed(self):
        r = self.run_diff({"a.png": h(b"a")}, {"a.png": h(b"a2")})
        self.assertEqual(r["changed"], [{"path": "a.png", "previous": h(b"a"), "new": h(b"a2")}])
        self.assertEqual(r["unchanged"], 0)

    def test_added_and_removed(self):
        r = self.run_diff({"old.js": h(b"o"), "keep": h(b"k")}, {"new.js": h(b"n"), "keep": h(b"k")})
        self.assertEqual(r["added"], ["new.js"])
        self.assertEqual(r["removed"], ["old.js"])
        self.assertEqual(r["unchanged"], 1)

    def test_evasion_a_one_byte_change_is_caught(self):
        r = self.run_diff({"doc.pdf": h(b"%PDF-1.7 x")}, {"doc.pdf": h(b"%PDF-1.7 y")})
        self.assertEqual([c["path"] for c in r["changed"]], ["doc.pdf"])

    def test_fail_closed_no_previous_manifest_is_a_baseline_not_a_crash(self):
        r = self.run_diff(None, {"a": h(b"a")})
        self.assertEqual(r["added"], ["a"])
        self.assertTrue(any("baseline" in n for n in r["notes"]))

    def test_fail_closed_unreadable_previous_is_noted(self):
        r = self.run_diff(None, {"a": h(b"a")}, raw_previous="<html>404</html>")
        self.assertTrue(any("unreadable" in n for n in r["notes"]))
        self.assertEqual(r["added"], ["a"])

    def test_fail_closed_other_algorithm_is_not_compared(self):
        r = self.run_diff(None, {"a": h(b"a")}, raw_previous=json.dumps({"algorithm": "md5", "files": {"a": "x"}}))
        self.assertTrue(any("not comparable" in n for n in r["notes"]))
        self.assertEqual(r["changed"], [], "hashes from another algorithm must not be reported as changes")

    def test_record_is_iso_utc_and_written(self):
        with tempfile.TemporaryDirectory() as d:
            p, n, out, summ = (Path(d) / x for x in ("p.json", "n.json", "out.json", "s.md"))
            p.write_text(json.dumps({"algorithm": "sha256", "files": {"a": h(b"1")}}))
            n.write_text(json.dumps({"algorithm": "sha256", "files": {"a": h(b"2")}}))
            r = subprocess.run([sys.executable, str(SCRIPT), str(p), str(n), "--out", str(out), "--summary", str(summ)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            rec = json.loads(out.read_text())
            self.assertRegex(rec["compared_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
            self.assertEqual(rec["changed"][0]["path"], "a")
            self.assertIn("`a`", summ.read_text())

    def test_diagnosis_only_never_blocks_even_on_missing_files(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "/nonexistent/prev.json", "/nonexistent/new.json"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "the diff must never fail a release")
        self.assertIn("not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
