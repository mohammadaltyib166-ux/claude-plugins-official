# Transitions on the timeline

Tool: `scripts/timeline.py` joins clips with FFmpeg `xfade` (video) and
`acrossfade` (audio), normalizing size, fps and audio first.

```bash
python3 scripts/timeline.py --list
python3 scripts/timeline.py --size 1920x1080 --fps 30 --out cut.mp4 \
    intro.mp4 fadeblack:0.6 part1.mp4 cut part2.mp4 slideleft:0.35 part3.mp4 fade:0.8 outro.mp4
```

Trim before joining (`-ss`/`-to` with re-encode for frame accuracy):
```bash
ffmpeg -ss 12.40 -to 31.95 -i raw.mp4 -c:v libx264 -crf 18 -c:a aac -b:a 192k part1.mp4
```

## The default is a cut

80-95% of edit points should be plain cuts. A transition is punctuation: it
says "new chapter", "time passed", "look, a change". Overused transitions make
a video feel amateur.

## Meaning -> transition

| You want to say | Use | Duration @30 fps |
|---|---|---|
| Next sentence, same idea | `cut` | 0 |
| New chapter / new step in a tutorial | `fade` or `fadeblack` | 0.4-0.6 s |
| Time passes, calm story beat | `fade`, `dissolve` | 0.6-1.0 s |
| Next item in a list, energetic | `slideleft` / `slideright` (RTL content: slide**right** reads "forward") | 0.25-0.35 s |
| Reveal, opening, "here it is" | `circleopen`, `radial` | 0.4-0.6 s |
| Zoom into a detail / hook energy | `zoomin` | 0.2-0.3 s |
| Before vs after, comparison | `wipeleft`/`wiperight`, `vertopen` | 0.4 s |
| Tech glitch, error, jump | `pixelize`, `hblur` | 0.2-0.3 s |
| End of video, out | `fadeblack` | 0.8-1.2 s |
| Flash / impact on a beat | `fadewhite` | 0.15-0.25 s |

Direction follows reading direction. `slideleft` moves the picture to the
left (the next clip enters from the right), which reads as "next" for English,
like turning a page in a left-to-right book. Arabic books turn the other way,
so for Arabic videos use `slideright`/`wiperight` for "next" and
`slideleft`/`wipeleft` for "back".

## Format rules

- **Reels/Shorts**: no transition longer than 0.35 s. Hard cuts on the beat.
  Transitions get an SFX (`whoosh`, `swoosh_short`) aligned to the transition start.
- **YouTube long**: cuts; one family of transitions for chapters only.
- **Tutorials**: never put a transition in the middle of a UI action. Cut on
  completed actions (after the click, after the page loads).
- **Interviews/podcasts**: cuts only; jump cuts on removed pauses are fine.

## Cut points

- Cut on silence (`silencedetect`) or on the end of a sentence, never mid-word.
- J-cut / L-cut (audio leads or trails the picture) makes talk feel smooth:
  start the next clip's audio 0.2-0.5 s before its picture. Do it by
  overlapping with `acrossfade` and cutting the picture (`cut`) at the later point,
  or with `adelay`/`atrim` in a custom graph.
- Match cut: end shot A and start shot B on similar shapes or motion; plain cut,
  no effect needed.
- Keep 2-4 frames of breath before and after speech in each clip.

## SFX pairing

| Transition | SFX (see sound.md) | Offset |
|---|---|---|
| slide*, zoomin, whip | `whoosh` or `swoosh_short` | start at transition start minus 0.05 s |
| fadewhite flash | `boom` or `swoosh_short` | on the flash |
| pixelize, hblur | `glitch` | on start |
| fade / fadeblack | none, or a soft riser leading in | - |

Transition times in the output: for a chain, the transition between clip k
and k+1 starts at `sum(durations of clips 1..k) - sum(previous transition
durations) - this duration`. `timeline.py` prints the expected total length;
compute cue times from the same arithmetic, or check with
`ffmpeg -i out.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null -`.
