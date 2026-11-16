# Programmatic graphics for video

Three layers, from cheap to expensive:
1. **FFmpeg filters** - boxes, bars, blur, picture-in-picture, overlays. Instant.
2. **ASS titles** - animated text (see typography.md). Instant.
3. **Blender shots** - real 3D (see camera-3d.md). Minutes per shot.

Use the cheapest layer that says the idea. Every graphic must point at, explain,
or structure something; none are decoration.

## FFmpeg recipes (all tested with this FFmpeg build)

Replace `D` with the clip duration in seconds; colors are `0xRRGGBB`.

```bash
# progress bar along the bottom (good for tutorials and Reels retention)
-vf "drawbox=x=0:y=ih-12:w=iw:h=12:color=white@0.25:t=fill,drawbox=x=0:y=ih-12:w='iw*t/D':h=12:color=0xFFD400:t=fill"

# highlight a region of the screen from 1 s to 4 s (point at a button, a line of code)
-vf "drawbox=x=400:y=200:w=300:h=180:color=0xFFD400:t=6:enable='between(t,1,4)'"

# blur a region (emails, tokens, faces, phone numbers)
-filter_complex "[0:v]crop=300:120:900:40,boxblur=20:2[b];[0:v][b]overlay=900:40"

# round face-cam bubble over a screen recording (bottom-right)
-i screen.mp4 -i face.mp4 -filter_complex "[1:v]scale=360:360:force_original_aspect_ratio=increase,crop=360:360,format=yuva420p,geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='255*lt(hypot(X-180,Y-180),180)'[pip];[0:v][pip]overlay=W-w-40:H-h-40:eof_action=pass"

# overlay a transparent 3D render (.mov ProRes 4444 / .webm VP9 alpha) in the center
-i base.mp4 -i shot.mov -filter_complex "[1:v]scale=480:-2[l];[0:v][l]overlay=(W-w)/2:(H-h)/2:eof_action=pass"
# start the overlay at 5 s instead of 0: add  setpts=PTS+5/TB  after scale

# split screen before | after
-i a.mp4 -i b.mp4 -filter_complex "[0:v]scale=960:540,crop=480:540[l];[1:v]scale=960:540,crop=480:540[r];[l][r]hstack"

# vertical (9:16) from horizontal: blurred fill behind the centered video
-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"

# zoom into a region for a few seconds (tutorial detail): use the camera tool
python3 scripts/camera_fx.py punch in.mp4 out.mp4 --at 12.0 --hold 3 --zoom 1.6 --focus 0.72 0.30
```

Arrows, icons, logos: overlay a PNG with transparency
(`-i arrow.png -filter_complex "[0:v][1:v]overlay=820:300:enable='between(t,2,5)'"`).
Animate position with expressions: `overlay=x='820+40*sin(t*6)':y=300` (a nudge).

## What to draw, by content

| Content | Graphic |
|---|---|
| Tutorial step | chapter card (ASS), progress bar, highlight box on the control being used, zoom to it |
| Code | zoom to the lines being edited; never cover code with captions |
| Statistic | big number callout (ASS, Anton/Lalezar, accent color), optional `boom` |
| Comparison | split screen, or before/after with `wipe*` transition |
| List of points | one point per beat: text pop-in + `pop` SFX, same position each time |
| Product / object | Blender orbit or arc shot, or the product photo on a 3D card |
| Screenshot / website | Blender image card (`type: image`, `thickness: 0.04`) with an orbit or dolly_in |
| Chapter / title | Blender text card (`type: text`, Arabic OK) or ASS chapter card |
| Sensitive info | blur region, always |

## Consistency rules

- One accent color for all highlights, numbers and emphasized words.
- Same corner and size for the face bubble for the whole video.
- Graphics enter and leave with the same motion style as the titles.
- Keep the 9:16 safe zones (typography.md) for every graphic in Reels.
