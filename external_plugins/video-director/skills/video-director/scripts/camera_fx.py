#!/usr/bin/env python3
"""Virtual camera moves on existing footage (FFmpeg only, no 3D).

Modes:
  push     slow continuous zoom in (or out with --to < --from) over the clip
  punch    instant zoom-ins at given times, held for --hold seconds (talking heads, reels)
  shake    handheld-style shake (subtle by default)
  kenburns slow zoom + drift for still images or static screen recordings

The frame is scaled up then cropped back to the original size, so nothing is
letterboxed. Zoom above ~1.25 visibly softens 1080p footage; record in 4K if
you plan strong punch-ins.

Usage:
  python3 camera_fx.py push in.mp4 out.mp4 --from 1.0 --to 1.12
  python3 camera_fx.py punch in.mp4 out.mp4 --at 3.2 7.8 12.5 --zoom 1.18 --hold 1.5
  python3 camera_fx.py shake in.mp4 out.mp4 --amount 0.6
  python3 camera_fx.py kenburns photo.jpg out.mp4 --duration 5 --size 1920x1080 --drift left
  add --focus X Y (0..1) to zoom toward a point instead of the center, e.g. --focus 0.5 0.35 for a face
"""
import argparse
import json
import subprocess
import sys


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    return s["width"], s["height"], float(d["format"].get("duration", 0) or 0)


def zoom_crop(W, H, zexpr, fx=0.5, fy=0.5, dx="0", dy="0"):
    # scale by Z each frame, then crop a WxH window around the focus point
    return (f"scale=w='2*trunc(iw*({zexpr})/2)':h='2*trunc(ih*({zexpr})/2)':eval=frame,"
            f"crop={W}:{H}:x='max(0,min(iw-{W},iw*{fx}-{W}*{fx}+({dx})))':"
            f"y='max(0,min(ih-{H},ih*{fy}-{H}*{fy}+({dy})))',setsar=1")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["push", "punch", "shake", "kenburns"])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--from", dest="z0", type=float, default=1.0)
    ap.add_argument("--to", dest="z1", type=float, default=1.12)
    ap.add_argument("--at", type=float, nargs="*", default=[])
    ap.add_argument("--zoom", type=float, default=1.18)
    ap.add_argument("--hold", type=float, default=1.5)
    ap.add_argument("--amount", type=float, default=0.5, help="shake strength 0..2")
    ap.add_argument("--focus", type=float, nargs=2, default=[0.5, 0.5])
    ap.add_argument("--duration", type=float, default=5.0, help="kenburns length")
    ap.add_argument("--size", default="1920x1080", help="kenburns output size")
    ap.add_argument("--drift", choices=["left", "right", "up", "down", "none"], default="none")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    fx, fy = a.focus

    if a.mode == "kenburns":
        W, H = map(int, a.size.lower().split("x"))
        frames = int(a.duration * a.fps)
        p = f"(on/{max(frames - 1, 1)})"
        ease = f"({p}*{p}*(3-2*{p}))"
        z = f"{a.z0}+({a.z1}-{a.z0})*{ease}"
        mx = {"left": f"-0.04*{ease}", "right": f"0.04*{ease}"}.get(a.drift, "0")
        my = {"up": f"-0.04*{ease}", "down": f"0.04*{ease}"}.get(a.drift, "0")
        vf = (f"scale={W * 4}:{H * 4}:force_original_aspect_ratio=increase,crop={W * 4}:{H * 4},"
              f"zoompan=z='{z}':x='iw*({fx}+{mx})-iw/zoom*{fx}':y='ih*({fy}+{my})-ih/zoom*{fy}':"
              f"d={frames}:s={W}x{H}:fps={a.fps},format=yuv420p")
        cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", a.input, "-vf", vf,
               "-frames:v", str(frames), "-c:v", "libx264", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", a.output]
    else:
        W, H, dur = probe(a.input)
        if a.mode == "push":
            p = f"(t/{max(dur, 0.1):.3f})"
            vf = zoom_crop(W, H, f"{a.z0}+({a.z1}-{a.z0})*{p}*{p}*(3-2*{p})", fx, fy)
        elif a.mode == "punch":
            if not a.at:
                sys.exit("punch needs --at times")
            # ease in over 0.12 s, hold, ease out over 0.2 s
            terms = [f"({a.zoom - 1:.4f})*clip((t-{t0:.3f})/0.12,0,1)*clip(({t0 + a.hold:.3f}-t)/0.2+1,0,1)"
                     f"*gte(t,{t0:.3f})" for t0 in a.at]
            vf = zoom_crop(W, H, "1+max(" + ",max(".join(terms) + ",0" + ")" * len(terms), fx, fy)
        else:  # shake: zoom slightly to have margin, then wander
            m = 1 + 0.03 * a.amount
            amp_x, amp_y = W * 0.008 * a.amount, H * 0.008 * a.amount
            dx = f"{amp_x:.2f}*(sin(t*7.1)+0.5*sin(t*13.7+1.3))"
            dy = f"{amp_y:.2f}*(sin(t*6.3+0.7)+0.5*sin(t*11.9+2.1))"
            vf = zoom_crop(W, H, f"{m}", fx, fy, dx, dy)
        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", a.input, "-vf", vf + ",format=yuv420p",
               "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium", "-c:a", "copy",
               "-movflags", "+faststart", a.output]
    if a.dry_run:
        print(" ".join(cmd))
        return
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
