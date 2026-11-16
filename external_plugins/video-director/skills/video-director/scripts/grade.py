#!/usr/bin/env python3
"""Color engine for FFmpeg: measure a clip, correct it, then apply a look.

Pipeline:  measure (signalstats)  ->  correct (levels, exposure, white balance,
saturation)  ->  look (named preset or .cube LUT, blended by --strength).

Commands:
  python3 grade.py looks
  python3 grade.py analyze in.mp4
  python3 grade.py apply in.mp4 out.mp4 --look warm_talk --strength 0.8 --preview cmp.png
  python3 grade.py apply b_cam.mp4 b_fixed.mp4 --match a_cam.mp4 --look none
  python3 grade.py apply in.mp4 out.mp4 --lut film.cube --strength 0.6
  python3 grade.py apply in.mp4 out.mp4 --look cinematic --no-auto --dry-run

Only FFmpeg/ffprobe and the Python standard library are used. Nothing is
downloaded. Output is written only to the path you give.
"""
import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile

LOOKS = {
    "none": ("No look; correction only.", ""),
    "clean_youtube": ("Neutral, crisp, slightly richer. Default for YouTube talking/tutorial.",
                      "eq=contrast=1.05:saturation=1.08,curves=all='0/0 0.25/0.23 0.75/0.77 1/1',unsharp=5:5:0.4"),
    "warm_talk": ("Warm, friendly skin tones. Vlogs, podcasts, personal stories.",
                  "colorbalance=rm=0.04:gm=0.0:bm=-0.04:rh=0.02:bh=-0.03,eq=saturation=1.05,"
                  "curves=all='0/0.03 0.5/0.52 1/0.98'"),
    "cinematic": ("Teal shadows, orange highlights, S-curve, vignette. Intros, stories, hooks.",
                  "colorbalance=rs=-0.06:bs=0.08:rh=0.07:bh=-0.07,curves=all='0/0.02 0.25/0.2 0.75/0.8 1/0.98',"
                  "eq=saturation=0.95,vignette=angle=PI/5"),
    "cool_tech": ("Cool, clean, modern. Tech, programming, product explainers.",
                  "colorbalance=rm=-0.02:bm=0.04:bs=0.04,eq=contrast=1.06:saturation=0.95"),
    "vibrant_reels": ("Punchy contrast and color for small phone screens. Reels/Shorts.",
                      "eq=contrast=1.1:saturation=1.3,curves=all='0/0 0.25/0.21 0.75/0.8 1/1',unsharp=5:5:0.6"),
    "documentary": ("Muted, lifted blacks, honest. Documentary, serious topics, history.",
                    "eq=saturation=0.8:contrast=0.97,curves=all='0/0.06 1/0.96',colorbalance=rh=0.02:bh=-0.02"),
    "night_moody": ("Darker, blue shadows, low saturation. Mystery, tension, night scenes.",
                    "eq=gamma=0.9:saturation=0.85,colorbalance=bs=0.08:rs=-0.04:bm=0.03"),
    "bw_dramatic": ("High-contrast black and white. Quotes, flashbacks, dramatic beats.",
                    "hue=s=0,curves=all='0/0 0.3/0.22 0.7/0.8 1/1',vignette=angle=PI/4"),
    "screen_safe": ("For screen recordings: tiny contrast only, UI colors stay true.",
                    "eq=contrast=1.02"),
}

KEYS = ["YMIN", "YLOW", "YAVG", "YHIGH", "YMAX", "UAVG", "VAVG", "SATAVG"]


def run(cmd, capture=True):
    return subprocess.run(cmd, capture_output=capture, text=True)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def analyze(path, samples=24):
    dur = duration(path) or 10.0
    fps = max(samples / dur, 0.05)
    with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as tf:
        out = tf.name
    vf = f"fps={fps:.4f},scale=480:-2,signalstats,metadata=mode=print:file={out}"
    r = run(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-an", "-f", "null", "-"])
    if r.returncode != 0:
        sys.exit(r.stderr)
    vals = {k: [] for k in KEYS}
    for line in open(out):
        m = re.search(r"lavfi\.signalstats\.(\w+)=([\d.]+)", line)
        if m and m.group(1) in vals:
            vals[m.group(1)].append(float(m.group(2)))
    os.unlink(out)
    if not vals["YAVG"]:
        sys.exit("no video frames measured")
    st = {k: round(statistics.median(v), 2) for k, v in vals.items() if v}
    st["frames"] = len(vals["YAVG"])
    return st


def norm(y):  # 8-bit limited-range luma -> 0..1
    return min(max((y - 16) / 219.0, 0.0), 1.0)


def diagnose(st):
    notes = []
    yl, yh, ya = norm(st["YLOW"]), norm(st["YHIGH"]), norm(st["YAVG"])
    if yh - yl < 0.6:
        notes.append("flat / low contrast")
    if ya < 0.32:
        notes.append("underexposed")
    elif ya > 0.62:
        notes.append("overexposed / washed out")
    cb, cr = (st["UAVG"] - 128) / 128, (st["VAVG"] - 128) / 128
    if cb > 0.025:
        notes.append("blue/cool cast")
    if cb < -0.025:
        notes.append("yellow/warm cast")
    if cr > 0.025:
        notes.append("red/magenta cast")
    if cr < -0.025:
        notes.append("green cast")
    if st["SATAVG"] < 18:
        notes.append("desaturated")
    elif st["SATAVG"] > 60:
        notes.append("very saturated")
    return notes or ["balanced"]


def correction(st, ref=None):
    """Return an FFmpeg filter string that corrects st (toward ref when given)."""
    parts = []
    yl, yh, ya = norm(st["YLOW"]), norm(st["YHIGH"]), norm(st["YAVG"])
    if ref:
        t_lo, t_hi, t_avg = norm(ref["YLOW"]), norm(ref["YHIGH"]), norm(ref["YAVG"])
        t_u, t_v, t_sat = ref["UAVG"], ref["VAVG"], ref["SATAVG"]
    else:
        t_lo, t_hi, t_avg, t_u, t_v, t_sat = 0.06, 0.92, 0.45, 128.0, 128.0, None
    # 1) levels: map the 10th/90th luma percentiles toward the targets
    span = max(yh - yl, 0.05)
    a = min(max((t_hi - t_lo) / span, 0.85), 1.4)
    black = yl - t_lo / a
    white = black + 1.0 / a
    if abs(a - 1) > 0.04 or abs(black) > 0.02:
        black, white = max(min(black, 0.4), -0.2), min(max(white, 0.6), 1.2)
        parts.append(f"colorlevels=rimin={black:.3f}:gimin={black:.3f}:bimin={black:.3f}:"
                     f"rimax={white:.3f}:gimax={white:.3f}:bimax={white:.3f}")
        ya = min(max((ya - black) * a, 0.01), 0.99)
    # 2) exposure (gamma) toward the target mid level
    if abs(ya - t_avg) > 0.03:
        g = math.log(ya) / math.log(t_avg)  # eq gamma >1 brightens
        g = min(max(g, 0.8), 1.3)
        parts.append(f"eq=gamma={g:.3f}")
    # 3) white balance from chroma averages
    cb, cr = (st["UAVG"] - t_u) / 128, (st["VAVG"] - t_v) / 128
    if abs(cb) > 0.015 or abs(cr) > 0.015:
        k = 1.6
        bm = max(min(-k * cb, 0.25), -0.25)
        rm = max(min(-k * cr, 0.25), -0.25)
        gm = max(min(k * (cb + cr) / 2, 0.15), -0.15)
        parts.append(f"colorbalance=rm={rm:.3f}:gm={gm:.3f}:bm={bm:.3f}")
    # 4) saturation
    sat = st["SATAVG"]
    if t_sat:
        f = min(max(t_sat / max(sat, 1), 0.6), 1.6)
        if abs(f - 1) > 0.05:
            parts.append(f"eq=saturation={f:.3f}")
    elif sat < 18:
        parts.append(f"eq=saturation={min(24 / max(sat, 1), 1.4):.3f}")
    return ",".join(parts)


def build_chain(corr, look_filter, strength):
    base = corr or "null"
    if not look_filter:
        return base
    if strength >= 0.999:
        return f"{base},{look_filter}"
    return (f"{base},format=yuv444p,split[c0][c1];[c1]{look_filter},format=yuv444p[g];"
            f"[c0][g]blend=all_mode=normal:all_opacity={strength:.3f},format=yuv420p")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("looks")
    p_an = sub.add_parser("analyze")
    p_an.add_argument("input")
    p_an.add_argument("--samples", type=int, default=24)
    p_ap = sub.add_parser("apply")
    p_ap.add_argument("input")
    p_ap.add_argument("output")
    p_ap.add_argument("--look", default="clean_youtube", choices=LOOKS)
    p_ap.add_argument("--lut", help=".cube file, used instead of --look")
    p_ap.add_argument("--strength", type=float, default=1.0, help="0..1 mix of the look")
    p_ap.add_argument("--no-auto", action="store_true", help="skip measurement-based correction")
    p_ap.add_argument("--match", help="reference clip: correct toward its exposure/color")
    p_ap.add_argument("--preview", help="write a before|after PNG and skip encoding unless --encode")
    p_ap.add_argument("--encode", action="store_true", help="with --preview, also encode the video")
    p_ap.add_argument("--at", type=float, help="preview time in seconds (default: middle)")
    p_ap.add_argument("--crf", type=int, default=18)
    p_ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.cmd == "looks":
        for k, (desc, _) in LOOKS.items():
            print(f"{k:15} {desc}")
        return
    if a.cmd == "analyze":
        st = analyze(a.input, a.samples)
        print(json.dumps({"stats": st, "diagnosis": diagnose(st), "correction": correction(st)},
                         ensure_ascii=False, indent=2))
        return

    corr = ""
    if not a.no_auto:
        st = analyze(a.input)
        ref = analyze(a.match) if a.match else None
        corr = correction(st, ref)
        print("diagnosis:", ", ".join(diagnose(st)), file=sys.stderr)
    if a.lut:
        if not os.path.isfile(a.lut):
            sys.exit(f"LUT not found: {a.lut}")
        look_f = f"lut3d=file='{a.lut}'"
    else:
        look_f = LOOKS[a.look][1]
    chain = build_chain(corr, look_f, max(0.0, min(a.strength, 1.0)))
    print("filter:", chain, file=sys.stderr)

    if a.preview:
        t = a.at if a.at is not None else duration(a.input) / 2
        fc = (f"[0:v]split[o][x];[x]{chain}[g];[o]scale=960:-2,setsar=1[o2];"
              f"[g]scale=960:-2,setsar=1[g2];[o2][g2]hstack")
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", a.input,
               "-filter_complex", fc, "-frames:v", "1", a.preview]
        if a.dry_run:
            print(" ".join(cmd))
        else:
            r = run(cmd)
            if r.returncode:
                sys.exit(r.stderr)
            print(f"preview: {a.preview} (left: before, right: after)")
        if not a.encode:
            return

    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", a.input, "-filter_complex", f"[0:v]{chain}[v]",
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.output]
    if a.dry_run:
        print(" ".join(cmd))
        return
    r = run(cmd, capture=False)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
