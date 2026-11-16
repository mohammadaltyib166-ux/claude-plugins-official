# Text in the video: captions, titles, lower thirds

Arabic needs letter shaping (joined letters) and right-to-left layout. In this
FFmpeg build `libass` (the `ass`/`subtitles` filters) does both correctly, with
`libfribidi` + `libharfbuzz`. Use ASS for anything Arabic. `drawtext` is fine for
Latin-only labels, numbers and timers.

## Fonts

```bash
python3 scripts/fetch_fonts.py --list
python3 scripts/fetch_fonts.py --dir fonts          # default set
python3 scripts/fetch_fonts.py --dir fonts --all
```
Always pass `fontsdir=fonts` to the `ass` filter, and use the **family name**
the script prints (e.g. `IBM Plex Sans Arabic`), not the file name.

| Role | Arabic | Latin |
|---|---|---|
| Captions, phone (Reels) | Almarai Bold | Poppins Bold |
| Captions, YouTube | Tajawal Bold, IBM Plex Sans Arabic | Poppins, Lato |
| Hook / thumbnail-style title | Lalezar | Anton, Bebas Neue |
| Tech / code tutorials | IBM Plex Sans Arabic (has Latin too) | IBM Plex Sans Arabic |
| Heritage, religious, literary | Amiri, Aref Ruqaa (titles only) | - |

Max two families per video. Mixed Arabic+English lines: pick a family that
covers both (IBM Plex Sans Arabic, Tajawal, Almarai) so English words match.

## Captions

```bash
python3 scripts/make_captions.py transcript.srt   --format youtube --font Tajawal --style clean --out subs.ass
python3 scripts/make_captions.py words.json       --format reels --font Almarai --style karaoke --position center --out subs.ass
python3 scripts/make_captions.py transcript.json  --video graded.mp4 --style boxed --font "IBM Plex Sans Arabic" --out subs.ass
ffmpeg -i graded.mp4 -vf "ass=subs.ass:fontsdir=fonts" -c:v libx264 -crf 18 -c:a copy captioned.mp4
```
Styles: `clean` (outline + shadow), `bold`, `boxed` (one box behind the event),
`karaoke` (needs word timings; the spoken word lights up in `--accent`).
Mark emphasis in the transcript with `*word*` -> accent color.

The script writes `Encoding: -1` in the style. Keep it: it makes libass lay out
the whole line together, so colored words inside an Arabic line stay in the
right order. Without it, words split by color tags come out reversed.

Reading rules:
- Max 2 lines; Reels max ~24 characters per line, YouTube ~42.
- Min 1.0 s on screen; Arabic reading speed ~12-15 characters per second.
- Break lines at phrase boundaries, never between a word and its article/preposition.
- Do not caption what is already written on screen (code, slide titles).

## Safe zones

| Format | Keep text out of | Caption position |
|---|---|---|
| YouTube 16:9 | outer 5%; bottom-right 20% in the last 20 s (end screen) | bottom, margin 8% of height |
| Reels / Shorts / TikTok 9:16 | top 14% (header), bottom 25% (caption + buttons), right 15% (like/share column) | lower-center at ~65-72% of height, or center |
| Square 1:1 | outer 7% | bottom, margin 8% |

## Titles and lower thirds (ASS snippets)

Make a titles file from the header `make_captions.py` writes (its `[Script Info]`
and `[V4+ Styles]` blocks), add a `Title` style, then the events. Keep
`Encoding` at `-1`. Times are `H:MM:SS.cc`. `\an` is the anchor (7 8 9 / 4 5 6 /
1 2 3 like a keypad). `\N` (line break) goes outside the `{...}` tag blocks.

```
Style: Title,Tajawal,72,&H00FFFFFF,&H0000D4FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,5,60,60,60,-1

; pop-in hook title, center, scales 60% -> 100% in 0.18 s, fades out
Dialogue: 0,0:00:00.20,0:00:02.40,Title,,0,0,0,,{\an5\fnLalezar\fs140\fad(0,250)\fscx60\fscy60\t(0,180,\fscx100\fscy100)}هل تعرف ما هي API؟

; lower third (1920x1080): name slides in from the right edge, role under it
Dialogue: 0,0:00:03.00,0:00:07.00,Title,,0,0,0,,{\an3\move(1980,980,1840,980,0,300)\fad(0,300)\fs54}م. أحمد علي\N{\fs38\b0}مطوّر برمجيات

; chapter card, center, slow fade
Dialogue: 0,0:01:12.00,0:01:14.50,Title,,0,0,0,,{\an5\fs96\fad(400,400)}الخطوة الثانية

; big number callout with accent color and a small bounce
Dialogue: 0,0:00:15.00,0:00:17.00,Title,,0,0,0,,{\an5\fs220\c&H00D4FF&\fnAnton\fad(80,200)\t(0,120,\fscx115\fscy115)\t(120,240,\fscx100\fscy100)}87%
```
Burn it after the captions: `-vf "ass=subs.ass:fontsdir=fonts,ass=titles.ass:fontsdir=fonts"`.
Colors in ASS are `&HBBGGRR&` (blue-green-red). `#FFD400` -> `&H00D4FF&`.

Motion guidance:
- Entrances 150-300 ms, exits 200-300 ms. Ease feels better than linear:
  `\t(t1,t2,accel,...)` with accel 0.5 (decelerate) for entrances.
- Reels: text appears exactly on the spoken word (use transcript timestamps).
- One animation style per video (all pop, or all slide, or all fade).

## drawtext (Latin labels, numbers, timers only)

```bash
# countdown timer top-right, Latin digits
-vf "drawtext=fontfile=fonts/Poppins-Bold.ttf:text='%{eif\:10-t\:d}':x=w-tw-40:y=40:fontsize=64:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=16:enable='lt(t,10)'"
```
