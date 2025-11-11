# dump_chart.py
# Print a chart: Key line + per-bar RN token and literal (as written).
# Minimal change: supports a directory path (alphabetical).

import sys
from pathlib import Path
from music21 import converter, harmony, roman
from rn_utils import prettify_literal, pretty_from_rn_and_literal, prefer_written_key, pretty_key_name

def dump_one(xml_path: str):
    s = converter.parse(xml_path)
    k = prefer_written_key(s)
    print(f"Key: {pretty_key_name(k)} (written/analyzed)")
    # Gather harmony objects in bar order
    # music21 harmony elements provide figure + measure info
    for h in s.recurse().getElementsByClass(harmony.ChordSymbol):
        try:
            mnum = h.measureNumber
        except Exception:
            mnum = None
        literal = prettify_literal(h.figure or "")
        # Try a romanNumeralFromChord against the key, fallback to blank
        try:
            rn = roman.romanNumeralFromChord(h, k)
            rn_token = pretty_from_rn_and_literal(rn.figure, literal)
        except Exception:
            rn_token = ""  # unknown
        if rn_token:
            print(f"m {mnum:>3}: {rn_token:<8} ({literal})")
        else:
            # still show literal even if RN failed
            print(f"m {mnum:>3}: {'':<8} ({literal})")

def main():
    if len(sys.argv) < 2:
        print("usage: python dump_chart.py <file-or-folder>")
        sys.exit(1)

    p = Path(sys.argv[1])
    if p.is_dir():
        files = sorted(
            [x for x in p.iterdir() if x.suffix.lower() in (".musicxml", ".xml", ".mxl")],
            key=lambda x: x.name.lower(),
        )
        for f in files:
            print(f"\n=== {f.name} ===")
            dump_one(str(f))
    else:
        dump_one(str(p))

if __name__ == "__main__":
    main()