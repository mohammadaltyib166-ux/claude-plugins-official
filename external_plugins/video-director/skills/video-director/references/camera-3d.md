# Camera, perspective and 3D

Two tools:
- `scripts/camera_fx.py` - virtual camera on existing footage (FFmpeg). Seconds.
- `scripts/blender_shot.py` - real 3D shots rendered by Blender Cycles on CPU. Minutes.

## Camera language (decide this first)

| Shot size | Shows | Use |
|---|---|---|
| Wide | whole scene | establish place, start of a section |
| Medium | waist up / whole object | explaining, default talking |
| Close-up | face / detail | emotion, emphasis, the key detail |
| Extreme close-up | eyes / one button | maximum emphasis, use rarely |

| Angle (`camera.angle`) | Feels | Use |
|---|---|---|
| `eye` | neutral, honest | default, tutorials |
| `low` | powerful, impressive | product hero, title, achievement |
| `high` | small, overview | showing a layout, a desk, a map |
| `birds_eye` / `overhead` | plan, analytic | diagrams, flat-lay, cooking, boards |
| `dutch` (tilted) | tension, energy, unease | Reels hooks, glitch moments; short |

| Lens (`camera.lens`, mm) | Perspective | Use |
|---|---|---|
| 18-24 | wide, exaggerated depth, distortion near edges | dramatic, energetic, close and big |
| 35 | natural wide | environments, screens on cards |
| 50 | neutral, like the eye | default |
| 85-135 | compressed, flattering, background blurs with `dof` | products, faces, premium feel |

| Move (`camera.move`) | Says | Use |
|---|---|---|
| `static` | calm, look at this | text cards, diagrams |
| `push_in_slow` | attention, importance growing | explaining a key idea |
| `dolly_in` | "look closer" | reveal a detail, intro title |
| `dolly_out` | "here is the big picture" | end of a section, context |
| `orbit` (`degrees`) | "see all sides" | products, objects, 3D models |
| `arc` | premium hero reveal (orbit + push) | product launch, channel intro |
| `crane_up` / `crane_down` | rise / descend, opening or closing | intros, outros |
| `truck_left` / `truck_right` | sideways discovery | a row of items, a timeline |
| `dolly_zoom` | vertigo, realization, shock | one dramatic moment only |

`ease`: `ease_in_out` (default, smooth), `ease_out` (fast start, soft landing;
good for titles), `ease_in`, `linear` (for loops), `smooth`.
`shake`: 0.2-0.4 subtle handheld; 1.0 strong (impacts).
`dof: true` + `fstop` 1.4-2.8 blurs foreground/background; costs render time.

## Footage moves (camera_fx.py)

```bash
python3 scripts/camera_fx.py push in.mp4 out.mp4 --from 1.0 --to 1.1          # slow push for a whole take
python3 scripts/camera_fx.py punch in.mp4 out.mp4 --at 4.2 9.8 --zoom 1.18 --hold 1.6 --focus 0.5 0.38
python3 scripts/camera_fx.py shake in.mp4 out.mp4 --amount 0.4
python3 scripts/camera_fx.py kenburns photo.jpg out.mp4 --duration 5 --size 1080x1920 --drift up
```
- Punch-ins at emphasis moments from DIRECTION.md (every 5-10 s on talking heads,
  every 2-3 s in Reels). `--focus` = where the face or the important region is (0..1).
- Above zoom ~1.25 on 1080p footage softness shows. 4K sources allow ~1.6.
- Combine with grading order: grade -> camera_fx -> captions (so captions don't zoom).

## Blender shots (blender_shot.py)

### Setup (once per cloud session)
```bash
python3 --version   # bpy 5.x wheels need Python 3.13
python3 -m venv ~/.bpy && ~/.bpy/bin/pip install bpy     # ~400 MB, from PyPI
~/.bpy/bin/python -c "import bpy; print(bpy.app.version_string)"
```
If the Python version differs, use `pip index versions bpy` and install the bpy
version whose wheel matches. Desktop Blender works too:
`blender -b -P scripts/blender_shot.py -- spec.json`.

Only Cycles on CPU works in a headless cloud container (EEVEE needs a GPU).

### Workflow: storyboard -> approve -> render
```bash
~/.bpy/bin/python scripts/blender_shot.py shot.json --storyboard 3    # first/middle/last frame, ~10-30 s
#  Read shot_storyboard.png, show the user, adjust, then:
~/.bpy/bin/python scripts/blender_shot.py shot.json                   # full render
```
Run long renders in the background (Bash `run_in_background`) and keep working.

Render cost on a 4-core cloud CPU (measured): `draft` (960x540, 16 spp) about
2-8 s per frame depending on the subject; a 3 s shot at 24 fps = 72 frames,
roughly 3-10 minutes. `final` (1920x1080, 64 spp) is about 6-10x slower.
Keep 3D inserts short (2-4 s), use 24 fps for them, render `draft` for Reels
(phones hide the difference), `final` only for hero shots.

### Spec examples
```json
{"output":"shots/intro.mp4","aspect":"9:16","quality":"draft","duration":2.5,"fps":24,
 "subject":{"type":"text","text":"الدرس الأول","font":"fonts/Lalezar-Regular.ttf","thickness":0.06},
 "color":"#FFD400","background":"#1B1030","lighting":"neon",
 "camera":{"move":"dolly_in","angle":"dutch","lens":35,"ease":"ease_out"}}
```
```json
{"output":"shots/site.mp4","aspect":"16:9","duration":3,"fps":24,
 "subject":{"type":"image","path":"screens/home.png","thickness":0.04},
 "background":"#0E1A2B","lighting":"soft",
 "camera":{"move":"orbit","angle":"high","degrees":40,"start_azimuth":-20,"lens":35}}
```
```json
{"output":"shots/product.mov","background":"transparent","duration":3,"fps":24,
 "subject":{"type":"model","path":"models/phone.glb"},"lighting":"studio","view":"agx",
 "camera":{"move":"arc","angle":"low","lens":85,"dof":true,"fstop":2.0}}
```
```json
{"output":"shots/step1.mp4","subject":{"type":"text3d","text":"STEP 1"},"color":"#2EC4B6",
 "lighting":"dramatic","camera":{"move":"dolly_zoom","angle":"eye"}}
```
```json
{"output":"shots/perfume_hero.mp4","aspect":"9:16","duration":4,"fps":24,"samples":8,
 "subject":{"type":"primitive","shape":"perfume","label":"LAYL","label_font":"fonts/BebasNeue-Regular.ttf"},
 "color":"#E0962F","background":"#07080B","floor_gloss":true,"lighting":"luxury",
 "camera":{"move":"orbit","angle":"low","lens":50,"degrees":60,"start_azimuth":-40}}
```
`camera.margin` (default 1.3) sets how much room is left around the subject:
0.5 is a close-up on the middle of the subject, 2+ leaves space for titles.

Subjects:
- `primitive`: cube, sphere, cylinder, cone, torus, monkey - placeholders, abstract intros.
- `primitive` + `"shape": "perfume"`: a glass perfume bottle with tinted liquid (`color`), gold neck and
  cap (`accent`), and an optional Latin `label` (`label_font` for a .ttf). For product ads without a model.
- `model`: .glb/.gltf (best), .obj, .fbx, .stl. Auto-scaled and centered. `"recolor": true` paints it `color`.
- `image`: any PNG/JPG on a card; `thickness` adds a device-like slab. Screenshots, photos, slides, thumbnails.
- `text`: any language, Arabic included, shaped by libass, as a flat card (with optional slab). Pass a `.ttf` path.
- `text3d`: extruded Latin text only; Arabic is refused (Blender cannot join Arabic letters).

Background `"transparent"` + output `.mov` (ProRes 4444) or `.webm` (VP9) gives
an alpha shot to overlay on footage; the floor becomes a shadow catcher.
`view`: `standard` keeps exact brand colors; `agx` is softer and photographic.

Lighting: `studio` (three-point, neutral), `soft` (bright, friendly, tutorials),
`dramatic` (side key + rim, dark), `neon` (pink/cyan, tech, Reels), `luxury` (warm key,
cool rim, tall strip lights for glass and metal edges, and a warm glow behind the subject;
perfume, jewelry, watches, premium products).
`floor_gloss: true` gives a reflective floor. `samples` overrides samples per pixel
(8 with denoising is enough for drafts). Glass subjects raise light bounces
automatically; expect about 5 s per draft frame at 540x960 on 4 cores.

Match the 3D shot to DIRECTION.md: same accent color, same font, background
close to the graded footage's tone, same aspect and fps as the edit (the
timeline tool converts fps, but matching avoids judder).
