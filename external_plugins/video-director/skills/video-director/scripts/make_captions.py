#!/usr/bin/env python3
"""Build an ASS subtitle file (Arabic-safe) for burning captions with FFmpeg/libass.

Why ASS: libass shapes Arabic letters (joins them) and lays out right-to-left
text correctly; FFmpeg drawtext is fine for short titles but not for captions.

Input (one of):
  * .srt file
  * .json list of segments: [{"start": 0.0, "end": 2.1, "text": "..."}]
  * .json list of words:    [{"start": 0.0, "end": 0.3, "word": "..."}]
    (word lists are grouped into short lines and can be highlighted word by word)

Emphasis: wrap words in *asterisks* to color them with --accent.

Usage:
  python3 make_captions.py subs.srt --format reels --font Almarai --out subs.ass
  python3 make_captions.py words.json --format reels --style karaoke --accent "#FFD400"
  ffmpeg -i in.mp4 -vf "ass=subs.ass:fontsdir=fonts" -c:a copy out.mp4
"""
import argparse
import json
import re
import subprocess
import sys

FORMATS = {  # (width, height)
    "youtube": (1920, 1080),
    "reels": (1080, 1920),
    "square": (1080, 1080),
}
ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")
RLM = "‏"


def hex_to_ass(h, alpha=0):
    h = h.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad color {h}")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ts(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    cs = int(round((s - int(s)) * 100))
    s = int(s)
    if cs == 100:
        s, cs = s + 1, 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def parse_srt_time(t):
    hh, mm, rest = t.strip().replace(",", ".").split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(rest)


def load(path):
    if path.lower().endswith(".srt"):
        raw = open(path, encoding="utf-8-sig").read()
        segs = []
        for block in re.split(r"\n\s*\n", raw.strip()):
            lines = block.strip().splitlines()
            idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
            if idx is None:
                continue
            a, b = lines[idx].split("-->")
            segs.append({"start": parse_srt_time(a), "end": parse_srt_time(b.split()[0]),
                         "text": " ".join(lines[idx + 1:]).strip()})
        return segs, None
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("segments") or data.get("words") or []
    if data and "word" in data[0]:
        return None, data
    return data, None


def group_words(words, max_chars, max_dur=3.0, gap=0.6):
    lines, cur = [], []
    for w in words:
        w = dict(w, word=str(w["word"]).strip())
        if not w["word"]:
            continue
        if cur:
            text_len = len(" ".join(x["word"] for x in cur + [w]))
            if (text_len > max_chars or w["end"] - cur[0]["start"] > max_dur
                    or w["start"] - cur[-1]["end"] > gap or cur[-1]["word"][-1:] in ".!?؟،,"):
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def is_rtl(text):
    return len(ARABIC.findall(text)) >= len(LATIN.findall(text)) and ARABIC.search(text)


def esc(text):
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def emphasize(text, accent, primary):
    return re.sub(r"\*(.+?)\*", lambda m: "{\\c" + accent + "}" + m.group(1) + "{\\c" + primary + "}", text)


def wrap(text, max_chars):
    if len(text) <= max_chars:
        return text
    words, out, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > max_chars:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    out.append(line)
    if len(out) > 2:  # keep at most two lines: rebalance by halves
        mid = len(words) // 2
        out = [" ".join(words[:mid]), " ".join(words[mid:])]
    return "\n".join(out)


def probe_size(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0:s=x", video],
                       capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split("x")[:2]
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--out", default="captions.ass")
    ap.add_argument("--format", choices=FORMATS, default="youtube")
    ap.add_argument("--video", help="probe width/height from this video instead of --format")
    ap.add_argument("--style", choices=["clean", "bold", "boxed", "karaoke"], default="clean")
    ap.add_argument("--font", default="Tajawal", help="family name, e.g. Tajawal, Almarai, Poppins")
    ap.add_argument("--size", type=float, help="font size in px (default depends on format)")
    ap.add_argument("--primary", default="#FFFFFF")
    ap.add_argument("--accent", default="#FFD400", help="emphasis/karaoke highlight color")
    ap.add_argument("--outline-color", default="#000000")
    ap.add_argument("--box-color", default="#000000")
    ap.add_argument("--position", choices=["bottom", "center", "top"], default="bottom")
    ap.add_argument("--max-chars", type=int, help="max characters per line")
    ap.add_argument("--offset", type=float, default=0.0, help="shift all times by seconds")
    a = ap.parse_args()

    W, H = probe_size(a.video) if a.video else FORMATS[a.format]
    vertical = H > W
    size = a.size or round(H * (0.045 if vertical else 0.055))
    max_chars = a.max_chars or (24 if vertical else 42)
    # safe zones: reels UI covers the bottom ~20% and the right edge
    margin_v = {"bottom": round(H * (0.26 if vertical else 0.08)),
                "center": 0,
                "top": round(H * (0.14 if vertical else 0.08))}[a.position]
    align = {"bottom": 2, "center": 5, "top": 8}[a.position]
    margin_lr = round(W * (0.10 if vertical else 0.06))

    primary = hex_to_ass(a.primary)
    accent = hex_to_ass(a.accent)
    outline = hex_to_ass(a.outline_color)
    bold = -1 if a.style in ("bold", "karaoke", "boxed") else 0
    if a.style == "boxed":
        # BorderStyle 4 (libass): one box behind the whole event; Outline sets padding
        border_style, outline_w, shadow = 4, round(size * 0.25), 0
        outline = hex_to_ass("#000000", alpha=0xFF)
        back = hex_to_ass(a.box_color, alpha=0x40)
    else:
        border_style = 1
        outline_w = round(size * (0.09 if a.style == "clean" else 0.13), 1)
        shadow = round(size * 0.04, 1)
        back = hex_to_ass("#000000", alpha=0x80)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{a.font},{size},{primary},{accent},{outline},{back},{bold},0,0,0,100,100,0,0,{border_style},{outline_w},{shadow},{align},{margin_lr},{margin_lr},{margin_v},-1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    segs, words = load(a.input)
    if words is not None:
        for line in group_words(words, max_chars):
            start, end = line[0]["start"] + a.offset, line[-1]["end"] + a.offset
            joined = " ".join(w["word"] for w in line)
            rtl = is_rtl(joined)
            if a.style == "karaoke":
                # one event per word: the line stays, the spoken word lights up
                for i, w in enumerate(line):
                    w_end = line[i + 1]["start"] if i + 1 < len(line) else w["end"]
                    parts = []
                    for j, x in enumerate(line):
                        t = esc(x["word"])
                        parts.append("{\\c" + accent + "}" + t + "{\\c" + primary + "}" if j == i else t)
                    txt = (RLM if rtl else "") + " ".join(parts)
                    events.append((w["start"] + a.offset, w_end + a.offset, txt))
            else:
                txt = emphasize(esc(wrap(joined, max_chars)), accent, primary)
                events.append((start, end, (RLM if rtl else "") + txt))
    else:
        for s in segs:
            text = str(s["text"]).strip()
            if not text:
                continue
            txt = emphasize(esc(wrap(text, max_chars)), accent, primary)
            if is_rtl(text):
                txt = RLM + txt.replace("\\N", "\\N" + RLM)
            events.append((s["start"] + a.offset, s["end"] + a.offset, txt))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(header)
        for st, en, txt in events:
            if en <= st:
                en = st + 0.3
            f.write(f"Dialogue: 0,{ts(st)},{ts(en)},Default,,0,0,0,,{txt}\n")
    print(f"wrote {a.out}: {len(events)} events, {W}x{H}, font {a.font} {size}px, style {a.style}")


if __name__ == "__main__":
    sys.exit(main())
