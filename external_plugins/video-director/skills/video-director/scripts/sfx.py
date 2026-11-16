#!/usr/bin/env python3
"""Sound design with FFmpeg: a small synthesized SFX kit, cue placement,
music ducking under the voice, and loudness normalization for platforms.

Commands:
  python3 sfx.py synth --dir sfx                 # whoosh, swoosh_short, pop, click, ding,
                                                 # riser, boom, glitch, typing, error, success
  python3 sfx.py mix in.mp4 out.mp4 \
      --cue 0.0:sfx/riser.wav:-8 --cue 2.0:sfx/boom.wav:-6 --cue 5.4:sfx/whoosh.wav:-10 \
      --music bed.mp3 --music-db -20 --duck --loudness youtube

Cue format: SECONDS:FILE[:GAIN_DB]. Gain is relative to the file's level.
--duck lowers the music while the original audio (the voice) is present.
--loudness: youtube/reels/podcast = -14/-14/-16 LUFS integrated, -1 dBTP.

The synthesized kit is a fallback. For richer sounds use the SFX library of
OpusClip (list_sound_effects / place_sound_effects) or your own licensed files.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

KIT = {
    "whoosh": ("anoisesrc=d=0.7:c=pink:a=0.6",
               "highpass=f=250,lowpass=f=5000,afade=t=in:d=0.4:curve=exp,"
               "afade=t=out:st=0.4:d=0.3:curve=log,volume=1.6", "transition, slide, fast movement"),
    "swoosh_short": ("anoisesrc=d=0.3:c=white:a=0.5",
                     "highpass=f=1200,lowpass=f=8000,afade=t=in:d=0.12,afade=t=out:st=0.12:d=0.18,volume=1.2",
                     "quick cut, text slide-in"),
    "pop": ("aevalsrc='0.9*sin(2*PI*(900-700*t/0.09)*t)*exp(-38*t)':d=0.15:s=48000", "",
            "text or icon appears, bullet point"),
    "click": ("aevalsrc='0.8*sin(2*PI*2400*t)*exp(-180*t)':d=0.05:s=48000", "highpass=f=800",
              "UI click, cursor, selection in a tutorial"),
    "ding": ("aevalsrc='0.5*sin(2*PI*1320*t)*exp(-5*t)+0.25*sin(2*PI*2640*t)*exp(-8*t)':d=1.2:s=48000", "",
             "correct answer, tip, key idea"),
    "success": ("aevalsrc='0.45*sin(2*PI*(if(lt(t,0.12),880,1320))*t)*exp(-4*(t-if(lt(t,0.12),0,0.12)))':d=0.8:s=48000",
                "", "task done, result shown"),
    "error": ("aevalsrc='0.4*sin(2*PI*220*t)*(lt(mod(t,0.18),0.12))*exp(-2*t)':d=0.5:s=48000", "lowpass=f=1500",
              "mistake, warning, wrong way"),
    "riser": ("aevalsrc='0.35*sin(2*PI*(150+900*t*t/4)*t)*(t/2)':d=2:s=48000",
              "afade=t=out:st=1.85:d=0.15", "build-up before a reveal or hook"),
    "boom": ("aevalsrc='0.95*sin(2*PI*(70-35*t)*t)*exp(-3.5*t)':d=1.5:s=48000", "lowpass=f=200,volume=1.5",
             "impact, title hit, big number"),
    "glitch": ("anoisesrc=d=0.35:c=white:a=0.6", "acrusher=bits=4:mode=log:aa=1,"
               "volume='if(lt(mod(t,0.07),0.035),1,0.1)':eval=frame,afade=t=out:st=0.25:d=0.1",
               "tech error, scene jump, cyber style"),
    "typing": ("aevalsrc='0.7*sin(2*PI*3000*t)*exp(-250*mod(t,0.11))*lt(mod(t,0.11),0.03)':d=1.2:s=48000",
               "highpass=f=1500,volume=0.8", "code or text being typed on screen"),
}
LOUDNESS = {"youtube": -14.0, "reels": -14.0, "podcast": -16.0, "broadcast": -23.0}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr.strip() or "ffmpeg failed")
    return r


def has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "json", path], capture_output=True, text=True)
    return bool(json.loads(r.stdout or "{}").get("streams"))


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def synth(dest):
    os.makedirs(dest, exist_ok=True)
    for name, (src, af, use) in KIT.items():
        out = os.path.join(dest, f"{name}.wav")
        chain = (af + "," if af else "") + "aformat=sample_rates=48000:channel_layouts=stereo,alimiter=limit=0.9"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src, "-af", chain, out])
        print(f"{name:13} {out:28} {use}")


def mix(a):
    inputs = ["-i", a.input]
    fc, mix_in = [], []
    voice = "[0:a]" if has_audio(a.input) else None
    if voice:
        fc.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo[voice]")
        voice = "[voice]"
    idx = 1
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
        fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={a.music_db}dB[mus0]")
        mus = "[mus0]"
        if a.duck and voice:
            fc.append(f"{voice}asplit=2[voice][vkey]")
            fc.append(f"{mus}[vkey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[mus]")
            mus = "[mus]"
        mix_in.append(mus)
        idx += 1
    for k, cue in enumerate(a.cue or []):
        parts = cue.split(":")
        t, path = float(parts[0]), parts[1]
        gain = float(parts[2]) if len(parts) > 2 else 0.0
        if not os.path.isfile(path):
            sys.exit(f"cue file not found: {path}")
        inputs += ["-i", path]
        ms = int(round(t * 1000))
        fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={gain}dB,"
                  f"adelay={ms}|{ms}[c{k}]")
        mix_in.append(f"[c{k}]")
        idx += 1
    if voice:
        mix_in.insert(0, voice)
    if not mix_in:
        sys.exit("nothing to mix: no audio in input, no --music, no --cue")
    target = LOUDNESS[a.loudness]
    dur = f"{duration(a.input):.3f}"
    fc.append("".join(mix_in) + f"amix=inputs={len(mix_in)}:duration=first:normalize=0:dropout_transition=0"
              "[aout]")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "mix.wav")
        # pass 1: render the mix, then measure it
        cmd = (["ffmpeg", "-y", "-v", "error"] + inputs +
               ["-filter_complex", ";".join(fc), "-map", "[aout]", "-t", dur, "-c:a", "pcm_s24le", wav])
        if a.dry_run:
            print(" ".join(f"'{x}'" if (";" in x or " " in x) else x for x in cmd))
            return
        run(cmd)
        r = run(["ffmpeg", "-v", "info", "-i", wav, "-af",
                 f"loudnorm=I={target}:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
        m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
        # pass 2: linear normalization with the measured values, mux with the untouched video
        norm = (f"loudnorm=I={target}:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                f"offset={m['target_offset']}:linear=true,aresample=48000")
        run(["ffmpeg", "-y", "-v", "error", "-i", a.input, "-i", wav, "-map", "0:v?", "-map", "1:a",
             "-af", norm, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", dur,
             "-movflags", "+faststart", a.output])
    print(f"wrote {a.output}: measured {m['input_i']} LUFS -> target {target} LUFS")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth")
    s.add_argument("--dir", default="sfx")
    sub.add_parser("list")
    m = sub.add_parser("mix")
    m.add_argument("input")
    m.add_argument("output")
    m.add_argument("--cue", action="append", help="SECONDS:FILE[:GAIN_DB]")
    m.add_argument("--music")
    m.add_argument("--music-db", type=float, default=-20.0)
    m.add_argument("--duck", action="store_true")
    m.add_argument("--loudness", choices=LOUDNESS, default="youtube")
    m.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "synth":
        synth(a.dir)
    elif a.cmd == "list":
        for k, (_, _, use) in KIT.items():
            print(f"{k:13} {use}")
    else:
        mix(a)


if __name__ == "__main__":
    main()
