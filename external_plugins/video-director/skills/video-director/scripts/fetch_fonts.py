#!/usr/bin/env python3
"""Download free (OFL) Arabic and Latin fonts for video titles and captions.

Fonts come from the google/fonts repository on GitHub. Only static font files
are listed: libass and FFmpeg pick weights reliably from static files, while
variable fonts often fall back to the regular weight.

Usage:
  python3 fetch_fonts.py                 # default set into ./fonts
  python3 fetch_fonts.py --dir fonts --all
  python3 fetch_fonts.py --only tajawal poppins
  python3 fetch_fonts.py --list
"""
import argparse
import os
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

# key: (family name as libass/ASS sees it, role, [files])
FONTS = {
    # Arabic
    "tajawal": ("Tajawal", "Arabic sans, clean and modern: captions, body titles",
                ["tajawal/Tajawal-Regular.ttf", "tajawal/Tajawal-Bold.ttf", "tajawal/Tajawal-ExtraBold.ttf"]),
    "almarai": ("Almarai", "Arabic sans, very legible on phones: reels captions",
                ["almarai/Almarai-Regular.ttf", "almarai/Almarai-Bold.ttf", "almarai/Almarai-ExtraBold.ttf"]),
    "ibmplexarabic": ("IBM Plex Sans Arabic", "Arabic + Latin, technical: tutorials, code, tech",
                      ["ibmplexsansarabic/IBMPlexSansArabic-Regular.ttf", "ibmplexsansarabic/IBMPlexSansArabic-Bold.ttf"]),
    "amiri": ("Amiri", "Arabic Naskh serif: religious, literary, documentary",
              ["amiri/Amiri-Regular.ttf", "amiri/Amiri-Bold.ttf"]),
    "lalezar": ("Lalezar", "Arabic heavy display: hooks, thumbnails-style titles",
                ["lalezar/Lalezar-Regular.ttf"]),
    "arefruqaa": ("Aref Ruqaa", "Arabic Ruqaa calligraphy: heritage, storytelling titles",
                  ["arefruqaa/ArefRuqaa-Regular.ttf", "arefruqaa/ArefRuqaa-Bold.ttf"]),
    # Latin
    "poppins": ("Poppins", "Latin geometric sans: YouTube titles and captions",
                ["poppins/Poppins-Regular.ttf", "poppins/Poppins-Bold.ttf"]),
    "bebas": ("Bebas Neue", "Latin condensed display, caps only: hooks, big numbers",
              ["bebasneue/BebasNeue-Regular.ttf"]),
    "anton": ("Anton", "Latin heavy condensed: reels hooks",
              ["anton/Anton-Regular.ttf"]),
    "lato": ("Lato", "Latin humanist sans: calm educational body text",
             ["lato/Lato-Regular.ttf", "lato/Lato-Bold.ttf"]),
}
DEFAULT = ["tajawal", "almarai", "ibmplexarabic", "lalezar", "poppins", "bebas"]


def fetch(key, dest):
    family, _, files = FONTS[key]
    ok = True
    for rel in files:
        out = os.path.join(dest, os.path.basename(rel))
        if os.path.exists(out) and os.path.getsize(out) > 0:
            continue
        try:
            with urllib.request.urlopen(BASE + rel, timeout=60) as r, open(out, "wb") as f:
                f.write(r.read())
        except Exception as e:  # network or 404
            print(f"  ! {rel}: {e}", file=sys.stderr)
            ok = False
    print(f"{'ok ' if ok else 'ERR'} {key:14} -> family \"{family}\"")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="fonts")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (fam, role, _) in FONTS.items():
            print(f"{k:14} {fam:22} {role}")
        return
    keys = a.only or (list(FONTS) if a.all else DEFAULT)
    bad = [k for k in keys if k not in FONTS]
    if bad:
        sys.exit(f"unknown font keys: {bad}; see --list")
    os.makedirs(a.dir, exist_ok=True)
    results = [fetch(k, a.dir) for k in keys]
    print(f"fonts dir: {os.path.abspath(a.dir)}  (pass fontsdir={a.dir} to the ass/subtitles filter)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
