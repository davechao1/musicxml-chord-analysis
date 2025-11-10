# scan_rn_patterns.py — exact, case-sensitive, adjacent RN sequence matcher
import csv, pathlib, argparse
from rn_utils import get_rn_rows

def find_matches(seq, pattern_tokens):
    """Return list of (barStart, matchStr, literalStr) for strict, adjacent matches."""
    hits = []
    n = len(pattern_tokens)
    for i in range(len(seq) - n + 1):
        window = seq[i:i+n]
        rn_seq = [w[3] for w in window]
        lit_seq = [w[4] for w in window]
        if rn_seq == pattern_tokens:
            hits.append((window[0][0], " ".join(rn_seq), " ".join(lit_seq)))
    return hits

def main():
    ap = argparse.ArgumentParser(description="Scan MusicXML files for RN patterns.")
    ap.add_argument("path", help="MusicXML file or folder")
    ap.add_argument("-p", "--pattern", action="append", required=True, help="Pattern (space-separated RN tokens)")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print matches live")
    args = ap.parse_args()

    base = pathlib.Path(args.path)
    files = list(base.glob("*.musicxml")) if base.is_dir() else [base]
    out_csv = "rn_matches.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Song","Path","Key","BarStart","Pattern","Match","LiteralChords"])

        for path in files:
            rows = get_rn_rows(str(path))
            if not rows: 
                continue
            song = path.stem
            key_name = rows[0][5]
            seq = rows
            for pat in args.pattern:
                toks = pat.split()
                hits = find_matches(seq, toks)
                if args.verbose:
                    print(f"✓ {song} [{pat}]: {len(hits)} hit(s)")
                    for b, m, lits in hits:
                        print(f"  → bar {b}: {m}")
                for b, m, lits in hits:
                    writer.writerow([song, str(path), key_name, b, pat, m, lits])
    if args.verbose:
        print(f"\nSaved: {out_csv}")

if __name__ == "__main__":
    main()