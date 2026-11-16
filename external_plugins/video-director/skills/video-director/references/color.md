# Color engine

Tool: `scripts/grade.py` (FFmpeg only). Order is always: **measure -> correct -> look**.
Correct first so the look lands on neutral footage; a look on top of a color cast
just makes a stronger cast.

## Commands

```bash
python3 scripts/grade.py looks                                  # list looks
python3 scripts/grade.py analyze in.mp4                         # stats + diagnosis + correction filter
python3 scripts/grade.py apply in.mp4 out.mp4 --look warm_talk --strength 0.8 --preview cmp.png
#   --preview writes before|after and stops; add --encode to also write the video
python3 scripts/grade.py apply camB.mp4 camB_fix.mp4 --match camA.mp4 --look none   # match two cameras
python3 scripts/grade.py apply in.mp4 out.mp4 --lut film.cube --strength 0.6        # your own LUT
python3 scripts/grade.py apply in.mp4 out.mp4 --look cinematic --no-auto --dry-run  # print command only
```

Always look at the `--preview` image before encoding a long video (Read the PNG).

## What the correction does

| Measure (signalstats) | Problem | Fix |
|---|---|---|
| YLOW..YHIGH span < 0.6 | flat, foggy | `colorlevels` stretch to 6%..92% |
| YAVG < 0.32 / > 0.62 | under / over exposed | `eq=gamma` toward 0.45 |
| UAVG, VAVG away from 128 | color cast | `colorbalance` midtones opposite to the cast |
| SATAVG < 18 | dull | `eq=saturation` up |

White balance uses the gray-world idea: it assumes the scene averages to gray.
It is wrong for scenes dominated by one color (green screen, sunset, a red
studio wall, a screen recording of a blue app). For those use `--no-auto`, or
`--match` against a well-balanced clip of the same shoot.

## Choosing the look

| Look | Use for | Avoid for |
|---|---|---|
| `clean_youtube` | default YouTube, explainers | already punchy footage |
| `warm_talk` | faces, vlogs, podcasts, personal stories | tech product shots |
| `cool_tech` | programming, AI, gadgets, data | food, family, warmth |
| `cinematic` | hooks, intros, stories, product reveals | long tutorials (tiring), screen recordings |
| `vibrant_reels` | Reels/Shorts on phones | skin-heavy close-ups at full strength (try 0.6) |
| `documentary` | serious topics, history, interviews | entertainment, kids |
| `night_moody` | mystery, tension, night | educational content |
| `bw_dramatic` | a quote, a flashback, one dramatic beat (short) | whole videos |
| `screen_safe` | screen recordings, slides, code | camera footage |

Strength: 1.0 for Reels and intros, 0.6-0.8 for talking heads, 0.3-0.5 when the
footage is already good.

## Rules

- Skin tones first: after grading, faces must not look orange, gray or green.
  If they do, lower `--strength` or switch to `warm_talk`/`clean_youtube`.
- Never grade screen recordings with camera looks; UI colors and code syntax
  colors must stay true. Grade the face cam and the screen separately, then composite.
- Grade **before** burning captions and titles, so text colors stay exact.
- One look for the whole video. Shots from different cameras: `--match` them to
  the main camera first, then apply the same look to all.
- Brand colors in graphics (titles, 3D renders) are added after grading and are
  not graded again.

## Manual recipes (when you need something the presets do not cover)

```bash
# lift shadows only
-vf "curves=all='0/0.05 0.3/0.32 1/1'"
# teal-orange split toning
-vf "colorbalance=rs=-0.1:bs=0.1:rh=0.1:bh=-0.1"
# keep reds, gray out everything else (selective color pop)
-vf "colorhold=color=red:similarity=0.25:blend=0.1"
# film grain
-vf "noise=alls=8:allf=t"
# check exposure with a waveform image
ffmpeg -ss 10 -i out.mp4 -vf "waveform=mode=column:filter=lowpass:scale=digital,scale=960:-2" -frames:v 1 wave.png
```
