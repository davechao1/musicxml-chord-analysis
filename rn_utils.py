# rn_utils.py — shared prettifier, simplifier, and RN extractor (minimal, consistent)
import re
import pathlib
from music21 import converter, harmony, roman, key as m21key

# --- Regex helpers ---
# Convert E-→Eb, F+→F# when +/- immediately follows the note name
_ROOT_PLUSMINUS = re.compile(r"\b([A-Ga-g])([+-])(?=$|[\s/()\d])")
_RN_HEAD = re.compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(.*)$")

def prettify_literal(fig: str) -> str:
    """Convert E-→Eb, F+→F#, trim spaces; keep add/sus phrases as-is."""
    if not fig:
        return ""
    def _swap(m):
        note, acc = m.group(1), m.group(2)
        return f"{note}{'b' if acc == '-' else '#'}"
    s = fig.strip()
    s = _ROOT_PLUSMINUS.sub(_swap, s)
    s = re.sub(r"\s{2,}", " ", s)
    return s

def pretty_key_name(k: m21key.Key) -> str:
    tonic = k.tonic.name.replace("-", "b").replace("+", "#")
    return f"{tonic} {k.mode}"

def simplify_rn_with_literal(rn_fig: str, literal: str) -> str:
    """
    Simplify music21 RN with minimal literal-guided corrections:
      - maj7 if literal says maj7 (M7/^7/Δ)
      - lowercase degree + '-7' if literal says m7/-7
      - V sus/add4-no3 → V7
      - handle 6/9; handle m6/6 from literal even if RN omits '6'
      - strip figured-bass clutter (65/64/43/42/75b3/5b3/7b5b3)
    """
    lit = (literal or "")
    lit_l = lit.lower()

    # literal flags
    lit_is_maj7 = bool(re.search(r"(?:maj7|\^7|Δ|\bM7\b)", literal or ""))
    # robust m7 detector: Gm7 / Gb m7 / G-7 etc.
    lit_is_min7 = bool(re.search(r"\b[a-g][#b]?\s*(?:m7|-7)\b", literal or "", re.I))
    lit_is_dom_sus = ("sus" in lit_l) or ("add 4 subtract 3" in lit_l)

    if not rn_fig:
        return ""

    t = rn_fig.replace(" ", "")
    t = re.sub(r"(?:\^7|M7|maj7)", "maj7", t)
    m = _RN_HEAD.match(t)
    if not m:
        return t
    acc, deg_raw, tail = m.groups()
    DEG = deg_raw.upper()
    is_minor_degree = deg_raw.islower()

    tail_low = tail.lower()
    # strip music21 figured-bass clutter
    tail_low = re.sub(r"(65|64|43|42|75b3|5b3|7b5b3)", "", tail_low)

    # --- literal-first overrides for 6/m6 (even if RN omitted '6') ---
    # Cm6, F#m6, etc. → lowercase degree + '-6'
    if re.search(r"\b[a-g][#b]?\s*m6\b", literal or "", re.I):
        return f"{acc}{DEG.lower()}-6"
    # C6, F#6, etc. (but not 6/9) → uppercase degree + 6
    if ("6/9" not in lit_l) and re.search(r"\b[a-g][#b]?6\b", literal or "", re.I):
        return f"{acc}{DEG}6"

    # literal overrides
    if lit_is_maj7:
        return f"{acc}{DEG}maj7"
    if lit_is_min7:
        return f"{acc}{DEG.lower()}-7"
    if (DEG == "V") and lit_is_dom_sus:
        return "V7"

    # RN-derived (with minimal normalization)
    if "maj7" in tail_low:
        return f"{acc}{DEG}maj7"
    if "ø7" in tail_low:
        return f"{acc}{(DEG.lower() if is_minor_degree else DEG)}ø7"
    if "o7" in tail_low or "°7" in tail_low:
        return f"{acc}{(DEG.lower() if is_minor_degree else DEG)}o7"
    if "6/9" in tail_low:
        return f"{acc}{DEG}6/9"
    # plain '6' (not 6/9) from RN tail
    if re.search(r"(?<!\d)6(?![49])", tail_low):
        return f"{acc}{DEG}6"
    # seventh chords
    if "7" in tail_low:
        return f"{acc}{(DEG.lower() + '-7') if is_minor_degree else DEG + '7'}"

    # no explicit quality → degree only
    return f"{acc}{DEG}"

def get_rn_rows(path: str):
    """
    Return ordered list of (bar, offset, idx, rn_simple, literal, key_name).
    Uses written key if present, else analyze('key').
    """
    p = pathlib.Path(path)
    s = converter.parse(str(p))

    # prefer written key (use Key objects if present; they preserve <mode>)
    keys = list(s.recurse().getElementsByClass(m21key.Key))
    if keys:
        k = keys[0]  # this is a music21.key.Key with correct .mode (major/minor)
    else:
        ksigs = list(s.recurse().getElementsByClass(m21key.KeySignature))
        if ksigs:
            try:
                k = ksigs[0].asKey()
            except Exception:
                k = s.analyze("key")
        else:
            k = s.analyze("key")

    key_name = pretty_key_name(k)
    rows = []
    idx = 0
    for h in s.recurse().getElementsByClass(harmony.Harmony):
        ch = h if isinstance(h, harmony.ChordSymbol) else getattr(h, "chordSymbol", None)
        if ch is None:
            continue
        lit = prettify_literal(ch.figure or "")
        try:
            rn_fig = roman.romanNumeralFromChord(ch, k).figure
        except Exception:
            rn_fig = ""
        simp = simplify_rn_with_literal(rn_fig, lit)
        bar = int(getattr(h, "measureNumber", 0) or 0)
        off = getattr(h, "offset", 0.0)
        rows.append((bar, float(off), idx, simp, lit, key_name))
        idx += 1

    rows.sort(key=lambda t: (t[0], t[1], t[2]))
    return rows