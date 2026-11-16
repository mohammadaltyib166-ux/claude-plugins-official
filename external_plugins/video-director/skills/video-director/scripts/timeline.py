#!/usr/bin/env python3
"""Join clips on a timeline with transitions (FFmpeg xfade + acrossfade).

The offset arithmetic for chained xfades is easy to get wrong by hand; this
script probes every clip and computes it. Clips are normalized to one size,
frame rate and audio format first, so mixed sources (phone, screen recording,
Blender render) join cleanly. Clips without audio get silence.

Timeline syntax: clip, then a transition token, then a clip, and so on.
  transition token = NAME:SECONDS   e.g. fade:0.5  slideleft:0.35  circleopen:0.6
                     cut            (hard cut, no overlap)
Audio crossfades for the same duration as the video transition.

Usage:
  python3 timeline.py --out final.mp4 intro.mp4 fade:0.6 a.mp4 cut b.mp4 slideleft:0.4 outro.mp4
  python3 timeline.py --size 1080x1920 --fps 30 --out reel.mp4 a.mp4 zoomin:0.3 b.mp4
  python3 timeline.py --list
  python3 timeline.py --dry-run ...     (print the FFmpeg command only)
"""
import argparse
import json
import subprocess
import sys

XFADE = """fade wipeleft wiperight wipeup wipedown slideleft slideright slideup slidedown
circlecrop rectcrop distance fadeblack fadewhite radial smoothleft smoothright smoothup
smoothdown circleopen circleclose vertopen vertclose horzopen horzclose dissolve pixelize
diagtl diagtr diagbl diagbr hlslice hrslice vuslice vdslice hblur fadegrays wipetl wipetr
wipebl wipebr squeezeh squeezev zoomin fadefast fadeslow hlwind hrwind vuwind vdwind
coverleft coverright coverup coverdown revealleft revealright revealup revealdown""".split()


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height,r_frame_rate",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"cannot read {path}: {r.stderr.strip()}")
    d = json.loads(r.stdout)
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        sys.exit(f"no video stream in {path}")
    return {"dur": float(d["format"]["duration"]), "w": v["width"], "h": v["height"],
            "audio": any(s.get("codec_type") == "audio" for s in streams)}


def parse(items):
    clips, trans = [], []
    expect_clip = True
    for it in items:
        is_trans = it == "cut" or (":" in it and it.split(":")[0] in XFADE)
        if expect_clip:
            if is_trans:
                sys.exit(f"expected a clip, got transition '{it}'")
            clips.append(it)
        else:
            if not is_trans:
                sys.exit(f"expected a transition (NAME:SECONDS or cut) after {clips[-1]}, got '{it}'"
                         f"; names: see --list")
            if it == "cut":
                trans.append(("cut", 0.0))
            else:
                name, sec = it.split(":", 1)
                trans.append((name, float(sec)))
        expect_clip = not expect_clip
    if expect_clip and clips:
        sys.exit("timeline cannot end with a transition")
    return clips, trans


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items", nargs="*")
    ap.add_argument("--out", default="timeline.mp4")
    ap.add_argument("--size", help="WxH (default: first clip)")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("cut (hard cut)\n" + " ".join(XFADE))
        return
    clips, trans = parse(a.items)
    if not clips:
        sys.exit("give at least one clip")
    info = [probe(c) for c in clips]
    W, H = (map(int, a.size.lower().split("x")) if a.size else (info[0]["w"], info[0]["h"]))
    W, H = W - W % 2, H - H % 2

    inputs, fc = [], []
    for i, (c, inf) in enumerate(zip(clips, info)):
        inputs += ["-i", c]
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={a.fps},"
                  f"format=yuv420p,trim=duration={inf['dur']:.3f},setpts=PTS-STARTPTS,settb=AVTB[v{i}]")
        if inf["audio"]:
            fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                      f"atrim=duration={inf['dur']:.3f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={inf['dur']:.3f}[a{i}]")

    vcur, acur, length = "v0", "a0", info[0]["dur"]
    for k, (name, d) in enumerate(trans, start=1):
        nxt = info[k]["dur"]
        if name != "cut":
            d = min(d, length * 0.9, nxt * 0.9)
        vo, ao = f"vx{k}", f"ax{k}"
        if name == "cut" or d <= 0:
            fc.append(f"[{vcur}][v{k}]concat=n=2:v=1:a=0,settb=AVTB[{vo}]")
            fc.append(f"[{acur}][a{k}]concat=n=2:v=0:a=1[{ao}]")
            length += nxt
        else:
            off = length - d
            fc.append(f"[{vcur}][v{k}]xfade=transition={name}:duration={d:.3f}:offset={off:.3f},settb=AVTB[{vo}]")
            fc.append(f"[{acur}][a{k}]acrossfade=d={d:.3f}:c1=tri:c2=tri[{ao}]")
            length = length + nxt - d
        vcur, acur = vo, ao

    cmd = (["ffmpeg", "-y", "-v", "error", "-stats"] + inputs +
           ["-filter_complex", ";".join(fc), "-map", f"[{vcur}]", "-map", f"[{acur}]",
            "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    print(f"timeline: {len(clips)} clips, {W}x{H}@{a.fps:g}, expected length {length:.2f}s", file=sys.stderr)
    if a.dry_run:
        print(" ".join(f"'{x}'" if (";" in x or " " in x) else x for x in cmd))
        return
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
