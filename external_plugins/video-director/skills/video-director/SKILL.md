---
name: video-director
description: Direct and finish videos (YouTube, Reels/Shorts, tutorials) with FFmpeg, OpusClip and Blender - understand the content, then decide and apply color grading, timeline transitions, Arabic/English captions and titles, programmatic graphics, sound effects and music, camera moves, and 3D shots with camera angles. Use when editing, grading, captioning, adding transitions, sound effects, motion graphics or 3D/camera shots to a video, or when planning how a video should look and sound.
---

# Video Director

You are the director and finishing editor. Tools do the work; your job is the
decisions: what this video needs, and what it does not. Every effect must help
the viewer understand or feel something; if it doesn't, leave it out.

## Tools

| Need | Tool | Reference |
|---|---|---|
| Understand the content: transcript, structure, emphasis | OpusClip connector (`get_transcript`), ffprobe, silence/scene detection | [content-analysis.md](references/content-analysis.md) |
| Color: measure, correct, look, match cameras | `scripts/grade.py` | [color.md](references/color.md) |
| Timeline + transitions | `scripts/timeline.py` | [transitions.md](references/transitions.md) |
| Captions + titles (Arabic-safe) | `scripts/make_captions.py`, `scripts/fetch_fonts.py`, ASS | [typography.md](references/typography.md) |
| Graphics: bars, highlights, PiP, blur, overlays | FFmpeg recipes | [motion-graphics.md](references/motion-graphics.md) |
| Sound effects, music ducking, loudness | `scripts/sfx.py`, OpusClip SFX library | [sound.md](references/sound.md) |
| Camera moves on footage | `scripts/camera_fx.py` | [camera-3d.md](references/camera-3d.md) |
| 3D shots, camera angles, lenses | `scripts/blender_shot.py` (Blender `bpy`) | [camera-3d.md](references/camera-3d.md) |

Scripts live in this skill's `scripts/` folder; run them by their full path.
They use only FFmpeg/ffprobe and the Python standard library (plus `bpy` for
`blender_shot.py`). They download nothing except `fetch_fonts.py` (fonts from the
google/fonts GitHub repository) and write only the output paths you give.
Every script has `--help`.

Read only the reference files the current task needs.

## Workflow

1. **Inputs.** Locate the footage and assets; make a working folder:
   `work/` (intermediate files), `shots/` (3D renders), `fonts/`, `sfx/`, `out/`.
   Run `ffprobe` on every source. If the user only has OpusClip access to the
   video, work through the connector and download its exports.
2. **Understand** (content-analysis.md). Transcript with timestamps, structure,
   emphasis moments, format, audience, tone. Classify the video and pick the
   direction preset.
3. **Write `DIRECTION.md`**: look, fonts, accent color, transition family,
   camera plan, 3D shots, SFX plan, and a timeline table. Show it to the user
   and wait for approval before long renders. Quick previews are fine before that.
4. **Cut**: trim and order clips, remove dead pauses (silencedetect), then join
   with `timeline.py` (cuts by default, transitions only where DIRECTION.md says).
5. **Color**: `grade.py apply ... --preview` -> check the image -> encode.
   Match cameras first (`--match`), then one look for the whole video.
   Screen recordings get `screen_safe` only.
6. **Camera**: punch-ins / pushes with `camera_fx.py` on the graded footage.
7. **3D shots**: `blender_shot.py --storyboard 3` -> show -> render in the
   background while you continue. Insert with `timeline.py` (opaque shots) or
   overlay (alpha `.mov`/`.webm`).
8. **Graphics + text**: overlays and highlights, then captions and titles last
   (`ass=` filters), so they are never graded, zoomed or blurred.
9. **Sound**: OpusClip `enhance_voice` / `place_sound_effects` when the project
   lives there; otherwise `sfx.py mix` with cues from DIRECTION.md, music
   ducked, loudness normalized for the platform.
10. **QA and deliver** (below).

Order matters: **cut -> grade -> camera -> 3D inserts -> graphics -> captions/titles -> sound/loudness -> export.**

## Working with OpusClip

OpusClip (AI Producer connector) is strong at: transcription, voice
enhancement, speaker framing (reframing 16:9 to 9:16), captions, B-roll and its
SFX library. Follow the connector's own instructions for uploading (upload card)
and exporting. Two ways to combine it with FFmpeg:
- **A (full control, preferred for Arabic):** OpusClip for transcript, voice,
  framing and SFX; export without burned captions; then grade, titles and
  captions here with ASS.
- **B (fast):** let OpusClip burn captions and place SFX; here only grade
  lightly (`--strength 0.5`), add 3D inserts, transitions and final loudness.
If downloading an export URL into this environment fails (network policy),
say so and ask the user for another way to provide the file.

## Formats and delivery

| Target | Size | fps | Video | Audio | Loudness |
|---|---|---|---|---|---|
| YouTube | 1920x1080 (or 3840x2160) | source (24/25/30/60) | H.264 `-crf 18 -preset slow -pix_fmt yuv420p` | AAC 192k 48 kHz | -14 LUFS, -1 dBTP |
| Reels / Shorts / TikTok | 1080x1920 | 30 | H.264 `-crf 19`, `-movflags +faststart` | AAC 192k | -14 LUFS |
| Square post | 1080x1080 | 30 | as above | as above | -14 LUFS |

Final export command shape:
```bash
ffmpeg -i work/final_av.mp4 -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart out/video_youtube.mp4
```
Avoid re-encoding many times: keep intermediates at `-crf 14-16` (or ProRes
for heavy multi-step work) and encode the delivery file once at the end.

## QA checklist (do it, don't skip it)

- Contact sheet: `ffmpeg -i out.mp4 -vf "fps=1/4,scale=480:-2,tile=4x4" -frames:v 1 sheet.png`, then Read it.
- Frames at every transition and title: no black flashes, no cut words, text in safe zones.
- Arabic text: letters joined, right-to-left order correct, colored words in place.
- Skin tones natural after grading; screen recordings not color-shifted.
- Audio: `ebur128` integrated within 1 LU of target; no clipping; music never covers speech.
- Duration and resolution match the platform; A/V sync at start and end.
- Report to the user what was done and what was not, with the output paths.

## Rules

- Ask before long renders (3D finals, full-length encodes over ~5 minutes) and
  before anything that uses connector credits.
- Never fetch music or SFX from random websites; use OpusClip's library, the
  user's files, or the local synthesized kit.
- Arabic text always goes through libass (ASS), never `drawtext`, never Blender `text3d`.
- Keep the user's original files untouched; write new files.
