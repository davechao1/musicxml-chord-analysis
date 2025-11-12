# rn_utils.py
from music21 import key as m21key
import re

# ---------------- Preferences ----------------
PRINT_69_STYLE = "69"  # change to "6/9" if you prefer

# ---------------- Literal prettifiers ----------------

# Convert E-→Eb, F+→F# when +/- follows pitch letter
_ROOT_PLUSMINUS = re.compile(r"\b([A-Ga-g])([+-])")

# Normalize odd "sus4" exports
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


# ---------------- RN normalization ----------------

# Unify maj7 spellings
MAJ7_ALIASES  = re.compile(r"(?:\^7|M7|maj7|Δ7|Δ)", re.I)
# A "plain 7" (dominant) in literals: not maj7, not m7, not ø7/o7
DOM7_PLAIN_RE = re.compile(r"(?<![øo])7(?![0-9])", re.I)

def normalize_rn(fig: str) -> str:
    """
    Normalize an RN string:
      - remove spaces, unify maj7 tokens
      - return <accidental><DEGREE><qual...> with DEGREE uppercased
    """
    t = (fig or "").replace(" ", "")
    t = MAJ7_ALIASES.sub("maj7", t)
    m = re.match(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(.*)$", t)
    if not m:
        return ""
    acc, deg, qual = m.groups()
    return f"{acc}{deg.upper()}{(qual or '')}"


# ---------------- Literal quality detectors ----------------

LIT_MINMAJ7_RE = re.compile(r"(?:m\(maj7\)|mmaj7|mMaj7|m\^7|mΔ)", re.I)
LIT_DIM_RE     = re.compile(r"(?:dim7|°7|o7)", re.I)
LIT_HALFDIM_RE = re.compile(r"(?:m7b5|ø7)", re.I)
# "Maj-family" (maj7/9/13 indications in the literal)
LIT_MAJ_FAM_RE = re.compile(r"(?:maj|\^|Δ)\s*(?:7|9|13)\b", re.I)

_DEGREE_HEAD = re.compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)")
# Strip RN inversion figures so they never leak into tokens
_INVERSION_FIGS_RE = re.compile(r"(?:65|64|63|62|54|53|43|42|32)")


def pretty_from_rn_and_literal(rn_fig: str, literal: str) -> str:
    """
    Literal-first RN prettyfier (STRICT + minimal changes):
      • Dominant detection: any literal with a plain '7' (not maj7/m7/ø7/o7)
        is treated as dominant (V7-family) and forces UPPERCASE degree.
      • Minor-7 detection: 'm7' anywhere in the literal marks minor 7
        (e.g., Am7, Em7/C). No word boundary required before m7.
      • Minor triad: 'Am' etc. with no maj7/m7/ø/o flags → lowercase degree only.
      • 6/9: prints as DEG + PRINT_69_STYLE (e.g., IV69).
      • Half-/dim: iiø7 / vii°7 handled from literal.
      • RN inversion figures are removed from the RN quality.
      • Falls back conservatively to the RN's own quality when literal
        doesn't say enough.
    """
    if not rn_fig:
        return rn_fig

    lit_pretty = prettify_literal(literal or "")
    rn = normalize_rn(rn_fig)

    m = _DEGREE_HEAD.match(rn)
    if not m:
        return rn_fig
    acc, DEG = m.group(1), m.group(2)
    qual_full = rn[len(m.group(0)):]
    qlow = _INVERSION_FIGS_RE.sub("", (qual_full or "").lower())

    lit_l = (lit_pretty or "").lower()

    # Families from literal
    is_minMaj7 = bool(LIT_MINMAJ7_RE.search(lit_l))
    is_maj_fam = bool(LIT_MAJ_FAM_RE.search(lit_l)) or is_minMaj7
    is_dim7    = bool(LIT_DIM_RE.search(lit_l))
    is_half    = bool(LIT_HALFDIM_RE.search(lit_l))

    # Minor traits from literal
    # Accept "Am", "Am6", "Am7", "Am9", "Am/C", etc.
    is_min_triad = bool(re.search(r"^[a-g][#b]?m(?=$|[/\s(]|[0-9])", lit_l))
    is_min7_lit  = bool(re.search(r"m7\b", lit_l))  # no leading \b — matches Am7 correctly
    is_min6_lit  = bool(re.search(r"m6\b", lit_l))

    # Robust 6/9: '6/9', '6-9', '69', '6 add 9'
    has_6_9 = bool(
        re.search(r"6\s*(?:/|-|\+|add|\()\s*9\)?", lit_l) or
        re.search(r"\b69\b", lit_l)
    )
    has_6_only = (not has_6_9) and (lit_l.endswith("6") or " 6" in lit_l)

    # Plain dominant '7' in literal (not maj7/m7/ø7/o7)
    is_dom7_lit = ("7" in lit_l) and not any(tag in lit_l for tag in ("maj7", "maj", "m7", "ø7", "o7"))

    # Minor-7 true only when literal says m7 and not overridden
    is_min7 = is_min7_lit and not (is_maj_fam or is_half or is_dim7)

    # Decide degree case: dominants MUST be uppercase degree
    if is_dom7_lit:
        DEG_case = DEG
    else:
        minorish_literal = (
            is_min7 or is_min6_lit or is_half or is_dim7 or
            (re.search(r"\bmin\b", lit_l) is not None and not is_maj_fam) or
            is_min_triad
        )
        DEG_case = DEG.lower() if minorish_literal else DEG

    # --- Build base token (priority order) ---
    if is_dim7:
        base = f"{acc}{DEG_case}o7"
    elif is_half:
        base = f"{acc}{DEG_case}ø7"
    elif is_minMaj7:
        base = f"{acc}{DEG_case}maj7"       # minor–major7 (degree already lower if minor)
    elif is_maj_fam:
        base = f"{acc}{DEG}maj7"            # maj-family keeps uppercase degree
    elif has_6_9:
        # treat 6/9 as major-family unless clearly minor triad literal
        if DEG_case.islower() or is_min_triad:
            base = f"{acc}{DEG_case}-6"     # conservative for minor 6/9 (rarely present literally)
        else:
            base = f"{acc}{DEG}{PRINT_69_STYLE}"
    elif has_6_only and not is_min6_lit:
        base = f"{acc}{DEG}6"
    elif is_min6_lit:
        base = f"{acc}{DEG_case}-6"
    elif is_min7:
        base = f"{acc}{DEG_case}-7"
    elif is_dom7_lit:
        base = f"{acc}{DEG}7"               # dominant 7 (degree uppercase)
    elif is_min_triad:
        base = f"{acc}{DEG_case}"           # Am → iii
    else:
        # RN fallback when literal doesn’t specify quality
        if "maj7" in qlow or "maj" in qlow:
            base = f"{acc}{DEG}maj7"
        elif "ø7" in qlow:
            base = f"{acc}{DEG}ø7"
        elif ("o7" in qlow) and ("ø" not in qlow):
            base = f"{acc}{DEG}o7"
        elif ("6/9" in qlow) or ("69" in qlow):
            base = f"{acc}{DEG}{PRINT_69_STYLE}"
        elif re.search(r"(?<!\d)6(?![/\d])", qlow):
            base = f"{acc}{DEG}6"
        elif ("7" in qlow) and not any(tag in qlow for tag in ("maj", "ø7", "o7")):
            base = f"{acc}{DEG}7"
        else:
            qsimple = re.sub(r"(65|64|43|42|32)", "", qlow)
            base = f"{acc}{DEG_case}{qsimple}" if qsimple else f"{acc}{DEG_case}"

    # Only add simple tensions for display (don’t change base quality)
    tens = []
    if "b9" in lit_l: tens.append("b9")
    if "#9" in lit_l: tens.append("#9")
    if tens:
        base += "(" + ",".join(tens) + ")"

    return base


# ---------------- Key helpers ----------------

def parse_key_arg(kstr: str) -> m21key.Key:
    """Accepts 'C', 'Eb', 'A-', 'F#', 'C minor'. (Note: '-' in input means flat.)"""
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
    """
    Prefer an explicit Key (with mode) if present; else fall back to
    KeySignature.asKey(); else analyze('key').
    """
    # 1) Explicit <key> (music21.key.Key) carries 'mode'
    try:
        k_objs = list(score.recurse().getElementsByClass(m21key.Key))
        if k_objs:
            return k_objs[0]
    except Exception:
        pass

    # 2) Fall back to first KeySignature
    try:
        ksigs = list(score.recurse().getElementsByClass(m21key.KeySignature))
        if ksigs:
            try:
                return ksigs[0].asKey()
            except Exception:
                pass
    except Exception:
        pass

    # 3) Last resort
    return score.analyze("key")

def pretty_key_name(k: m21key.Key) -> str:
    """Convert E- / E+ naming to Eb / E#, keep 'major'/'minor'."""
    tonic = k.tonic.name.replace("-", "b").replace("+", "#")
    return f"{tonic} {k.mode}"