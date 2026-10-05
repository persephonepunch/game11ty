#!/usr/bin/env python3
"""
SB-24: compare this release's SHA-256 manifest with the last deployed one.

    python3 scripts/manifest_diff.py PREVIOUS NEW [--out diff.json] [--summary summary.md]

Diagnosis and record only. It reports which files were added, removed or
changed (same path, different bytes) and writes that record; it never blocks a
release and never changes a file. Deciding whether a change was expected is a
person's job. Exit status is always 0, even when a manifest is missing or
unreadable: that is reported as a note in the record instead.

Standard library only.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path


def load(path, notes, label):
    """Return {path: sha256} from a manifest, or None with a note saying why."""
    p = Path(path)
    if not p.is_file():
        notes.append(f"{label} manifest not found: {path}")
        return None
    try:
        m = json.loads(p.read_text())
    except (ValueError, UnicodeDecodeError) as e:
        notes.append(f"{label} manifest unreadable: {e}")
        return None
    if not isinstance(m, dict) or not isinstance(m.get("files"), dict):
        notes.append(f"{label} manifest has no files map")
        return None
    if m.get("algorithm") != "sha256":
        notes.append(f"{label} manifest algorithm is {m.get('algorithm')!r}, not 'sha256'; hashes not comparable")
        return None
    return m["files"]


def diff(previous, new):
    notes = []
    old = load(previous, notes, "previous")
    cur = load(new, notes, "new")
    record = {"algorithm": "sha256", "compared_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "added": [], "removed": [], "changed": [], "unchanged": 0, "notes": notes}
    if cur is None:
        return record
    if old is None:
        notes.append("no comparable previous release: every file is listed as added (baseline)")
        old = {}
    record["added"] = sorted(set(cur) - set(old))
    record["removed"] = sorted(set(old) - set(cur))
    for path in sorted(set(cur) & set(old)):
        if cur[path] != old[path]:
            record["changed"].append({"path": path, "previous": old[path], "new": cur[path]})
        else:
            record["unchanged"] += 1
    return record


def summary(r):
    lines = ["## Release diff (SB-24)", "",
             f"{len(r['added'])} added · {len(r['removed'])} removed · {len(r['changed'])} changed · {r['unchanged']} unchanged", ""]
    for n in r["notes"]:
        lines.append(f"> {n}")
    for title, items in (("Changed", [c["path"] for c in r["changed"]]), ("Added", r["added"]), ("Removed", r["removed"])):
        if items:
            lines += ["", f"**{title}**", ""] + [f"- `{p}`" for p in items[:200]]
            if len(items) > 200:
                lines.append(f"- … and {len(items) - 200} more (see the JSON record)")
    return "\n".join(lines) + "\n"


def main(argv):
    args, opts = [], {}
    it = iter(argv)
    for a in it:
        if a in ("--out", "--summary"):
            opts[a] = next(it, None)
        else:
            args.append(a)
    if len(args) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 0
    r = diff(*args)
    text = json.dumps(r, indent=1) + "\n"
    if opts.get("--out"):
        Path(opts["--out"]).write_text(text)
    if opts.get("--summary"):
        with open(opts["--summary"], "a") as f:
            f.write(summary(r))
    print(summary(r), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
