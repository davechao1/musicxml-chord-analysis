# scan_rn_patterns.py
# Strict-by-default scanner with family wildcards; folder support (alphabetical).

import argparse
from pathlib import Path
from typing import List, Tuple, Dict
from music21 import converter, harmony, roman
from rn_utils import prettify_literal, pretty_from_rn_and_literal, prefer_written_key

# --- Pattern token syntax ---
# Exact (strict match, no wildcard):
#     IVmaj7   I6   V7   ii-7   iv-6   viiø7   vio7
#     → Matches only that exact quality (no substitutions).
#
# Family wildcards (add * after a numeral):
#     I*   IV*      → any major-family chord (I, I6, Imaj7, I69, Imaj9, etc.)
#     ii*  iv*      → any minor-family chord (ii, ii-6, ii-7, ii-9, ii–maj7, etc.)
#     V7*           → any dominant-family chord with a 7 present
#                      (V7, V9, V13, V7b9, V7#9, V7sus4, V7b9#11, etc.)
#
# Built-in dominant flexibility:
#     A plain “7” quality (e.g. V7) automatically matches any dominant-family
#     chord with added tensions or alterations — no * needed.
#
# Accidental prefixes supported:
#     bVII7, #IV*, etc.
#
# Wildcards affect only quality (extensions, tensions, alterations),
# not root or function (I* won’t match ii or V).

_TOKEN_RE = __import__("re").compile(
    r"""
    ^                                           # start
    [b#]?(?:VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)  # degree
    (?:maj7|-7|7|ø7|o7|6/9|-6|6)?               # optional quality
    \*?                                         # optional family wildcard
    $                                           # end
    """,
    __import__("re").VERBOSE,
)

_DEGREE_HEAD = __import__("re").compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)")

def _degree_only(tok: str) -> str:
    m = _DEGREE_HEAD.match(tok or "")
    return m.group(0) if m else ""

def _suffix_only(tok: str) -> str:
    head = _degree_only(tok)
    return tok[len(head):] if head else tok

def _is_major_family(tok: str) -> bool:
    deg = _degree_only(tok)
    if not deg or not deg[0].isupper():
        return False
    suf = _suffix_only(tok).lower()
    return suf in ("", "6", "maj7", "6/9")

def _is_minor_family(tok: str) -> bool:
    deg = _degree_only(tok)
    if not deg or deg[0].isupper():
        return False
    suf = _suffix_only(tok).lower()
    # include minor–major7 per your request
    return suf in ("", "-6", "-7", "maj7")

def _is_dom7_family(tok: str) -> bool:
    deg = _degree_only(tok)
    if not deg or not deg[0].isupper():
        return False
    suf = _suffix_only(tok).lower()
    # Dominant must contain '7' but not maj/ø/o; alterations/sus are normalized into literal only
    return ("7" in suf) and ("maj" not in suf) and ("ø" not in suf) and ("o" not in suf)

def parse_pattern(pat: str) -> List[str]:
    toks = pat.strip().split()
    for t in toks:
        if not _TOKEN_RE.match(t):
            raise SystemExit(f"Pattern error: Bad token syntax: '{t}'")
    return toks

def extract_rn_sequence(xml_path: str) -> List[Tuple[int, str, str]]:
    """
    Return a sequence of (barNumber, rnToken, literal) for a single file.
    rnToken is produced by rn_utils.pretty_from_rn_and_literal to keep tokens canonical.
    """
    s = converter.parse(xml_path)
    k = prefer_written_key(s)
    out: List[Tuple[int, str, str]] = []
    for h in s.recurse().getElementsByClass(harmony.ChordSymbol):
        try:
            mnum = h.measureNumber
        except Exception:
            mnum = None
        lit = prettify_literal(h.figure or "")
        try:
            rn = roman.romanNumeralFromChord(h, k)
            tok = pretty_from_rn_and_literal(rn.figure, lit)
        except Exception:
            tok = ""
        if tok:
            out.append((mnum or 0, tok, lit))
        else:
            out.append((mnum or 0, "", lit))
    # stable, in-bar order is already given by recursion; ensure numeric bar order just in case
    out.sort(key=lambda x: (x[0]))
    return out

def find_pattern_matches(seq: List[Tuple[int, str, str]], pat_tokens: List[str]) -> List[Dict]:
    hits: List[Dict] = []
    n = len(pat_tokens)
    if n == 0:
        return hits
    # sliding window
    for i in range(0, len(seq) - n + 1):
        window = seq[i : i + n]  # [(bar, tok, lit), ...]
        match = True
        for ptok, (_, stok, _slit) in zip(pat_tokens, window):
            if ptok.endswith("*"):
                base = ptok[:-1]
                if _degree_only(base) != _degree_only(stok):
                    match = False
                    break
                # Family selection by case / desired suffix
                suf = _suffix_only(base).lower()
                if base and base[0].isupper():
                    # uppercase: major family unless specifically '7*' -> dominant family
                    if suf == "7":
                        if not _is_dom7_family(stok):
                            match = False; break
                    else:
                        if not _is_major_family(stok):
                            match = False; break
                else:
                    # lowercase: minor family (includes minor–maj7)
                    if not _is_minor_family(stok):
                        match = False; break
            else:
                if stok != ptok:
                    match = False
                    break
        if match:
            bar0 = window[0][0]
            lits = [l for (_b, _t, l) in window]
            toks = [t for (_b, t, _l) in window]
            hits.append({"bar": bar0, "tokens": toks, "literals": lits})
    return hits

def iter_musicxml_paths(base: Path):
    if base.is_file():
        if base.suffix.lower() in (".musicxml", ".xml", ".mxl"):
            return [base]
        return []
    files = []
    for ext in ("*.musicxml", "*.xml", "*.mxl"):
        files.extend(base.rglob(ext))
    return sorted([p for p in files if p.is_file()], key=lambda p: p.name.lower())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="file or directory of MusicXML")
    ap.add_argument("-p", "--pattern", dest="patterns", action="append", required=True,
                    help="Pattern like 'ii-7 V7 I*' or 'IVmaj7 I6 III7'. Repeatable.")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-o", "--output", dest="csv_out", default=None,
                    help="Optional CSV output path")
    ap.add_argument("--show-literals", dest="show_literals", action="store_true",
                    help="Include literal chords column in CSV")
    args = ap.parse_args()

    paths = iter_musicxml_paths(Path(args.path))
    if not paths:
        raise SystemExit("No MusicXML files found.")

    # parse all patterns up front
    patlist = []
    for p in args.patterns:
        toks = parse_pattern(p)
        patlist.append((p, toks))

    import csv, sys as _sys
    writer = None
    if args.csv_out:
        fout = open(args.csv_out, "w", newline="")
        writer = csv.writer(fout)
        header = ["Title", "Path", "Key", "Bar", "Pattern", "Tokens"]
        if args.show_literals:
            header.append("Literals")
        writer.writerow(header)

    for xmlp in paths:
        try:
            s = converter.parse(str(xmlp))
            k = prefer_written_key(s)
            # best-effort title
            title = (s.metadata.title if s.metadata and s.metadata.title else xmlp.stem)
            seq = extract_rn_sequence(str(xmlp))
        except Exception as e:
            print(f"× {xmlp.stem}: ERROR ({e})")
            continue

        for pat_str, toks in patlist:
            hits = find_pattern_matches(seq, toks)
            if args.verbose:
                print(f"✓ {xmlp.stem} [{pat_str}]: {len(hits)} hit(s)")
                for h in hits:
                    line = f"  → bar {h['bar']}: " + " ".join(h["tokens"])
                    if args.show_literals:
                        line += "  |  " + " | ".join(h["literals"])
                    print(line)
            if writer and hits:
                for h in hits:
                    row = [title, str(xmlp), f"{k.tonic.name.replace('-', 'b').replace('+', '#')} {k.mode}",
                           h["bar"], pat_str, " ".join(h["tokens"])]
                    if args.show_literals:
                        row.append(" | ".join(h["literals"]))
                    writer.writerow(row)

    if writer:
        fout.close()

if __name__ == "__main__":
    main()