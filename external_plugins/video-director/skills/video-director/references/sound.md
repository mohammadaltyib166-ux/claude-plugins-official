# Sound design

Two sources of sound effects:
1. **OpusClip** (AI Producer connector): its SFX library is the richest. Use
   `list_sound_effects` to browse and `place_sound_effects` to place them on its
   project; `enhance_voice` cleans the voice. Read the tools' own descriptions
   first; names may change.
2. **Local kit** - `scripts/sfx.py synth` makes 11 simple sounds with FFmpeg
   (no download, no license questions). Good enough for pops, clicks, whooshes,
   risers and hits; not for realistic foley.

```bash
python3 scripts/sfx.py list
python3 scripts/sfx.py synth --dir sfx
python3 scripts/sfx.py mix in.mp4 out.mp4 \
   --cue 0.0:sfx/riser.wav:-8 --cue 1.8:sfx/boom.wav:-4 --cue 4.2:sfx/pop.wav:-12 \
   --music music.mp3 --music-db -22 --duck --loudness youtube
```
`mix` keeps the original voice, adds cues at exact times, ducks the music under
the voice (`--duck`), and normalizes loudness in two passes (measure, then
linear gain). Output is within about 1 LU of the target unless true peak
limits it.

## Where sounds go

| Event on screen | SFX | Level vs voice |
|---|---|---|
| Hook build-up (first 1-2 s) | `riser` | -8 dB |
| Hook title lands / big number | `boom` | -4 to -6 dB |
| Slide / zoom transition | `whoosh`, `swoosh_short` | -10 dB |
| Text or icon pops in, bullet point | `pop` | -12 dB |
| Click in a tutorial | `click` | -14 dB |
| Typing on screen | `typing` | -16 dB |
| Key idea, tip | `ding` | -12 dB |
| Correct result | `success` | -10 dB |
| Wrong way, warning | `error` | -12 dB |
| Glitch / jump transition | `glitch` | -12 dB |

Timing: place the SFX 1-2 frames (0.03-0.06 s) **before** the visual event; the
ear expects sound slightly early. For transitions, start at the transition start.

Density by format:
- Reels/Shorts: every cut and every text pop can have a sound.
- YouTube educational: only chapters, key ideas, and results.
- Interviews, serious, religious content: none, or a soft riser on the intro.

## Music

- Music sits at -20 to -24 dB under speech with `--duck`; -14 to -18 dB when
  there is no voice (intros, montage).
- Pick the tempo from the edit pace: Reels 110-140 BPM; tutorials 80-100 BPM,
  calm; stories: ambient pads.
- Cut picture on the beat for montages: get beat times from the music track
  (`ffmpeg -i music.mp3 -af "silencedetect=n=-30dB:d=0.05" -f null -` gives rough
  onsets for percussive tracks) and place cuts there.
- Only use music the user has the rights to (their library, OpusClip's
  library, or royalty-free tracks they provide). Never fetch random music.

## Voice

- Clean voice first (OpusClip `enhance_voice`), or locally:
  `-af "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=10:release=200"`.
- Remove long pauses before adding SFX (cut list from `silencedetect`).

## Delivery loudness

| Platform | Integrated | True peak |
|---|---|---|
| YouTube, Reels, TikTok (`youtube`/`reels`) | -14 LUFS | -1 dBTP |
| Podcast (`podcast`) | -16 LUFS | -1 dBTP |
| Broadcast (`broadcast`) | -23 LUFS | -1 dBTP |

Check: `ffmpeg -i out.mp4 -af ebur128 -f null - 2>&1 | grep -A1 Integrated`.
