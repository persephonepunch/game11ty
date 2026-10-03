#!/usr/bin/env python3
"""
Mutation check for the no_std GLB parser (SB-19 reference implementation).
Each mutant swaps a safe operation for an unchecked one, or deletes a check.
Every mutant must make `cargo test` fail. Run: python3 mutate.py
"""
import shutil, subprocess, sys
from pathlib import Path

LIB = Path(__file__).parent / "src" / "lib.rs"
SOURCE = LIB.read_text()
MUTANTS = [
    ("magic bytes not checked", 'if data.get(0..4) != Some(b"glTF") { return Err(GlbError::NotGlb); }', ""),
    ("total length not checked", "if u32_at(data, 8)? as usize != data.len() { return Err(GlbError::LengthLie); }", ""),
    ("chunk type not checked", 'if data.get(16..20) != Some(b"JSON") { return Err(GlbError::NotGlb); }', ""),
    ("bounds-checked read replaced by raw indexing", "data.get(20..end).ok_or(GlbError::LengthLie)", "Ok(&data[20..end])"),
    ("header read replaced by raw indexing",
     "let b = data.get(at..at.checked_add(4).ok_or(GlbError::Truncated)?).ok_or(GlbError::Truncated)?;",
     "let b = &data[at..at + 4];"),
]

def main():
    survivors = 0
    try:
        for what, old, new in MUTANTS:
            if old not in SOURCE:
                print(f"STALE    {what}"); survivors += 1; continue
            LIB.write_text(SOURCE.replace(old, new, 1))
            r = subprocess.run(["cargo", "test", "--quiet"], cwd=LIB.parent.parent, capture_output=True)
            killed = r.returncode != 0
            survivors += not killed
            print(f"{'killed  ' if killed else 'SURVIVED'} SB-19  {what}")
    finally:
        LIB.write_text(SOURCE)  # always restore the real source
    print(f"\n{len(MUTANTS) - survivors}/{len(MUTANTS)} mutants killed")
    sys.exit(1 if survivors else 0)

if __name__ == "__main__":
    main()
