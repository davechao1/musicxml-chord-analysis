# rn_utils.py
from music21 import key as m21key
import re

# ---------- Output preferences ----------
# Choose how to print major 6/9 chords: "6/9" or "69"
PRINT_69_STYLE = "69"   # set to "6/9" if you prefer IV6/9

# ---------- Literal prettifiers ----------

# Convert E-→Eb, F+→F# when +/- immediately follows the pitch letter
_ROOT_PLUSMINUS = re.compile(r"\b([A-Ga-g])([+-])")

# Normalize odd sus4 phrases from some exports
_SUS4_VARIANTS = [
    re.compile(r"\badd\s*4\s*(?:subtract|minus|no|omit)\s*3\b", re.I),
    re.compile(r"\badd4\s*(?:subtract|minus|no|omit)\s*3\b", re.I),
    re.compile(r"\badd\s*11\s*(?:no|omit)\s*3\b", re.I),
    re.compile(r"\bsus\s*4\b", re.I),
]

def _root_plus_minus_to_acc(text: str) -> str:
    def _swap(m):
        note, acc = m.group(1), m.group(2)
        return f"{note}{'b' if acc == '-' else '#'}"
    return _ROOT_PLUSMINUS.sub(_swap, text)

def _normalize_sus4(text: str) -> str:
    s = text
    for pat in _SUS4_VARIANTS:
        s = pat.sub("sus4", s)
    s = re.sub(r"\b(sus4)(\s+\1\b)+", r"\1", s, flags=re.I)
    return s

def prettify_literal(literal: str) -> str:
    if not literal:
        return literal
    s = literal.strip()
    s = _root_plus_minus_to_acc(s)
    s = _normalize_sus4(s)
    s = re.sub(r"\s{2,}", " ", s)
    return s


# ---------- RN normalization ----------

MAJ7_ALIASES   = re.compile(r"(?:\^7|M7|maj7|Δ7|Δ)", re.I)
DOM7_PLAIN_RE  = re.compile(r"(?<![øo])7(?![0-9])", re.I)   # plain 7 (not ø7/o7)

def normalize_rn(fig: str) -> str:
    """
    Normalize a music21 RN figure minimally:
      - remove spaces
      - unify maj7 aliases to 'maj7'
      - uppercase degree token (I..VII), preserve accidental (#/b)
    """
    t = (fig or "").replace(" ", "")
    t = MAJ7_ALIASES.sub("maj7", t)
    m = re.match(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(.*)$", t)
    if not m:
        return ""
    acc, deg, qual = m.groups()
    return f"{acc}{deg.upper()}{(qual or '')}"


# ---------- Literal quality detectors ----------

LIT_MINMAJ7_RE = re.compile(r"(?:m\(maj7\)|mmaj7|mMaj7|m\^7|mΔ)", re.I)
LIT_DIM_RE     = re.compile(r"(?:dim7|°7|o7)", re.I)
LIT_HALFDIM_RE = re.compile(r"(?:m7b5|ø7)", re.I)
# Major family: allow maj7/9/13 (or ^/Δ with those numbers). Avoid bare 'M'.
LIT_MAJ_FAM_RE = re.compile(r"(?:maj|\^|Δ)\s*(?:7|9|13)\b", re.I)

# ---------- RN prettifier guided by the literal ----------

_DEGREE_HEAD = re.compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)")
# Strip RN inversion figures so they never leak into tokens
_INVERSION_FIGS_RE = re.compile(r"(?:65|64|63|62|54|53|43|42|32)")

def pretty_from_rn_and_literal(rn_fig: str, literal: str) -> str:
    """
    Literal-first RN:
      - maj family → ...maj7 (Fmaj7 → Imaj7)
      - minor triad → lowercase degree only (Am → iii); minor6 → -6; minor7 → -7
      - dim → o7, half-dim → ø7
      - 6/9-family prints as DEG + PRINT_69_STYLE (IV69 or IV6/9)
      - plain '7' in literal (e.g., F7, F7/A) → DOM7
      - strip RN inversion digits (65/64/43/42/32) from RN quality
    """
    if not rn_fig:
        return rn_fig

    lit = prettify_literal(literal or "")
    rn  = normalize_rn(rn_fig)

    m = _DEGREE_HEAD.match(rn)
    if not m:
        return rn_fig
    acc, DEG = m.group(1), m.group(2)
    qual_full = rn[len(m.group(0)):]
    qlow = _INVERSION_FIGS_RE.sub("", (qual_full or "").lower())

    lit_l = (lit or "").lower()
    rn_minor_deg = bool(re.match(r"^[b#]?(vii|vi|v|iv|iii|ii|i)", (rn_fig or "")))

    # families from literal
    is_minMaj7   = bool(LIT_MINMAJ7_RE.search(lit_l))
    is_maj_fam   = bool(LIT_MAJ_FAM_RE.search(lit_l)) or is_minMaj7
    is_dim7      = bool(LIT_DIM_RE.search(lit_l))
    is_half      = bool(LIT_HALFDIM_RE.search(lit_l))

    # minor traits from literal
    # allow digits/slashes right after 'm' (Am, Am6, Am7, Am/C)
    is_min_triad = bool(re.search(r"^[a-g][#b]?m(?=$|[/\s(]|[0-9])", lit_l))
    is_min7_lit  = (re.search(r"m7\b", lit_l) is not None)
    is_min7      = is_min7_lit and not (is_maj_fam or is_half or is_dim7)

    # robust 6/9 (covers 'Bb6 add 9', 'Bb6add9', 'Bb6/9', 'Bb69', etc.)
    has_6_9 = bool(
        re.search(r"6\s*(?:/|-|\+|add|\()\s*9\)?", lit_l) or
        re.search(r"\b69\b", lit_l)
    )
    has_6_only = (not has_6_9) and (lit_l.endswith("6") or " 6" in lit_l)

    # literal-level plain dominant 7 (not maj7 / m7 / ø7 / o7)
    is_dom7_lit = ("7" in lit_l) and not any(tag in lit_l for tag in ("maj7", "maj", "m7", "ø7", "o7"))

    # If RN shows lowercase degree and RN quality has '7' or literal says m7 → minor7
    if (not is_min7) and rn_minor_deg and (("7" in qlow) or is_min7_lit):
        is_min7 = True

    # decide degree case
    minorish_literal = is_min7 or is_half or is_dim7 or (("min" in lit_l) and not is_maj_fam) or is_min_triad
    deg = DEG.lower() if (minorish_literal or rn_minor_deg) else DEG

    # ----- Build base token (order matters) -----
    if is_dim7:
        base = f"{acc}{deg}o7"
    elif is_half:
        base = f"{acc}{deg}ø7"
    elif is_minMaj7:
        base = f"{acc}{deg}maj7"
    elif is_maj_fam:
        base = f"{acc}{deg}maj7"
    elif is_min7:
        base = f"{acc}{deg}-7"
    elif has_6_9:
        if minorish_literal or is_min_triad:
            # conservative for minor 6/9 in RN (often not encoded distinctly)
            base = f"{acc}{deg}-6"
        else:
            base = f"{acc}{DEG}{PRINT_69_STYLE}"
    elif has_6_only:
        base = f"{acc}{deg}-6" if (minorish_literal or is_min_triad) else f"{acc}{DEG}6"
    elif is_dom7_lit:
        base = f"{acc}{DEG}7"      # treat literal 'F7' / 'F7/A' as DOM7
    elif is_min_triad:
        base = f"{acc}{deg}"       # Am → iii
    else:
        # RN fallback when literal doesn’t specify the quality
        if "maj7" in qlow or "maj" in qlow:
            base = f"{acc}{DEG}maj7"
        elif "ø7" in qlow:
            base = f"{acc}{DEG}ø7"
        elif ("o7" in qlow) and ("ø" not in qlow):
            base = f"{acc}{DEG}o7"
        elif ("6/9" in qlow) or ("69" in qlow):
            base = f"{acc}{DEG}{PRINT_69_STYLE}"
        elif re.search(r"(?<!\d)6(?![049])", qlow):
            base = f"{acc}{DEG}6"
        elif ("7" in qlow) and not any(x in qlow for x in ("maj", "ø7", "o7")):
            base = f"{acc}{DEG}7"
        else:
            base = f"{acc}{DEG}"

    return base


# ---------- Key helpers ----------

def parse_key_arg(kstr: str) -> m21key.Key:
    """Accepts 'C', 'Eb', 'A-', 'F#', 'C minor'. (Note: '-' means flat.)"""
    kstr = kstr.strip().replace("-", "b")
    parts = kstr.split()
    if len(parts) == 1:
        return m21key.Key(parts[0])
    elif len(parts) == 2:
        tonic, mode = parts[0], parts[1].lower()
        return m21key.Key(tonic, mode=mode)
    else:
        raise ValueError(f"Unrecognized key string: {kstr}")

def prefer_written_key(score) -> m21key.Key:
    """Prefer the first written KeySignature; else fall back to analyze('key')."""
    try:
        ksigs = list(score.recurse().getElementsByClass(m21key.KeySignature))
    except Exception:
        ksigs = []
    if ksigs:
        try:
            return ksigs[0].asKey()
        except Exception:
            pass
    return score.analyze("key")

def pretty_key_name(k: m21key.Key) -> str:
    """Convert E- / E+ to Eb / E#, keep 'major'/'minor'."""
    tonic = k.tonic.name.replace("-", "b").replace("+", "#")
    return f"{tonic} {k.mode}"