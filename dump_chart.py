# dump_chart.py — print simplified RN + literal for inspection
from rn_utils import get_rn_rows

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Dump simplified Roman numerals per measure.")
    ap.add_argument("path", help="MusicXML file (.xml/.musicxml/.mxl)")
    args = ap.parse_args()

    rows = get_rn_rows(args.path)
    if not rows:
        print("No harmony elements found.")
        return

    key_name = rows[0][5]
    print(f"Key: {key_name} (written/analyzed)")
    for bar, off, idx, simp, lit, _ in rows:
        if not simp:
            simp = "(—)"
        print(f"m {bar:2d}: {simp:<8} ({lit})")

if __name__ == "__main__":
    main()