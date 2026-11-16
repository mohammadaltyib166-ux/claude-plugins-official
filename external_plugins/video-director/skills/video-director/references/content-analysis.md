# Understanding the content

Every creative choice in this skill comes from this step. Do it first, write it
down in `DIRECTION.md`, and show it to the user before rendering anything heavy.

## 1. Get the words and the timing

Preferred: OpusClip (AI Producer connector), when it is connected.
- Upload with `open_upload_card` + `wait_upload`, then `start_transcribe_project`.
- `get_transcript` gives the spoken text with timestamps. Keep it as
  `work/transcript.json` (segments or words with start/end in seconds).
- Tool names can change; read the connector's own tool descriptions first.

Without OpusClip: ask the user for the script or an `.srt`; or watch frames
yourself (`ffmpeg -i in.mp4 -vf fps=1/5,scale=480:-2,tile=4x3 sheet.png` and Read
the sheet) and describe what is on screen.

Also measure the footage:
```bash
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate -of compact in.mp4
python3 scripts/grade.py analyze in.mp4            # exposure, color cast, saturation
ffmpeg -i in.mp4 -af silencedetect=n=-35dB:d=0.6 -f null - 2>&1 | grep silence_   # pauses = cut points
ffmpeg -i in.mp4 -vf "select='gt(scene,0.35)',showinfo" -f null - 2>&1 | grep pts_time  # shot changes
```

## 2. Build the content map

Answer these, in this order, in `DIRECTION.md`:

| Question | Why it matters |
|---|---|
| Topic in one sentence | Drives palette, fonts, 3D subject |
| Format: YouTube long / Reels-Shorts / tutorial | Aspect, pace, caption size, safe zones |
| Audience (age, expertise, language: Arabic / English / mixed) | Font family, reading speed, jargon on screen |
| Goal: teach / persuade / entertain / announce | How loud the edit is |
| Tone: calm, serious, energetic, playful, luxurious, technical | Look, transition family, SFX kit |
| Structure with timestamps: hook, sections, key points, CTA | Where transitions and titles go |
| Emphasis moments: numbers, warnings, punchlines, reveals, steps | Punch-ins, SFX cues, callouts |
| What must be shown, not only said (UI, product, diagram, place) | B-roll, screenshots on 3D cards, Blender shots |
| Constraints: brand colors, existing intro, length limit | Overrides everything else |

## 3. Classify and pick the direction preset

| Content type | Pace (avg shot) | Look | Transitions | Captions | Camera | SFX density |
|---|---|---|---|---|---|---|
| YouTube educational / explainer | 4-8 s | `clean_youtube` or `cool_tech` | cuts; `fade` 0.4 s between chapters | clean, bottom | `push` slow, punch on key points | low: pop for bullets, ding for key idea |
| Programming / software tutorial | screen-driven | `screen_safe` on screen, `cool_tech` on face cam | cuts; `slideleft` 0.3 s between steps | boxed, top or bottom away from the code | zoom to the region being edited | click, typing, success/error |
| Talking head / podcast clip | 3-6 s | `warm_talk` | cuts; jump cuts on pauses | bold, center-low | punch-ins every 5-10 s on emphasis | very low |
| Reels / Shorts | 1-2.5 s | `vibrant_reels` | cuts, `zoomin`/`slide*` 0.2-0.3 s, whip | karaoke word-by-word, center | punch, shake on hits | high: whoosh on every transition, pop on text |
| Story / documentary | 5-10 s | `cinematic` or `documentary` | `fade`, `fadeblack` 0.6-1 s, dissolve | clean, small | slow push, arc in 3D shots | riser before reveals, boom on titles |
| Product / announcement | 2-4 s | `cinematic` or brand LUT | `circleopen`, `slide*`, match cuts | bold titles, few captions | 3D orbit/arc of the product | riser + boom, whoosh |
| Religious / heritage / literary | 6-12 s | `documentary` or `warm_talk` | `fade`, `dissolve` only | Amiri or Aref Ruqaa titles | slow push, static | none or very soft |

Rules:
- One look per video. One transition family per video (plus plain cuts).
- Every effect must answer "what does this help the viewer understand or feel?".
  If there is no answer, cut it.
- The hook (first 3 s) gets the most energy; tutorials calm down after the hook.

## 4. Write DIRECTION.md

Template (keep it short; it is the brief every later step follows):

```markdown
# Direction: <title>
Format: Reels 1080x1920, 30 fps, 45 s | Language: Arabic (Gulf), English terms
Audience: beginners in programming | Goal: teach one idea | Tone: energetic, friendly
Look: vibrant_reels, strength 0.8 | Fonts: Almarai (captions), Lalezar (hook)
Accent color: #FFD400 | Background for 3D: #101418
Transitions: cut + slideleft 0.25 s, whoosh on each
Camera: punch-in 1.15 on emphasis; 3D intro: text card "الدرس الأول", dolly_in, neon
SFX: riser 0-1.8 s, boom 1.8 s, pop on each bullet, success at the end

## Timeline
| Time | Content | Visual | Text on screen | SFX |
|---|---|---|---|---|
| 0.0-2.0 | Hook: "هل تعرف ما هي API؟" | 3D title shot | hook text, Lalezar | riser, boom |
| 2.0-9.5 | Definition | face cam, punch at 4.2 | captions; "*API*" accent | pop 4.2 |
| ... | | | | |
```

Ask the user to approve or change DIRECTION.md before long renders (3D shots,
full-length encodes). Small previews (storyboards, a 5 s graded sample) are fine
to make without asking.
