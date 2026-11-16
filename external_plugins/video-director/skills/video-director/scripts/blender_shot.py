#!/usr/bin/env python3
"""Render a 3D shot with Blender (Cycles, CPU) from a small JSON spec.

Subjects: primitive shape, imported model (.glb/.gltf/.obj/.fbx/.stl), image or
screenshot on a card, text card (any language, Arabic included), extruded 3D
text (Latin only: Blender cannot shape Arabic).
Camera: angle preset + move (orbit, dolly, crane, truck, dolly zoom, arc...),
lens in mm, easing, depth of field, handheld shake. Every frame is keyed from
Python, so moves are exact and repeatable.

Run with the Blender Python module (pip package "bpy"):
  ~/.bpy/bin/python blender_shot.py spec.json
  ~/.bpy/bin/python blender_shot.py spec.json --storyboard 3    # 3 stills, fast approval
  ~/.bpy/bin/python blender_shot.py '{"subject":{"type":"primitive","shape":"monkey"}}'
or with desktop Blender:
  blender -b -P blender_shot.py -- spec.json

Spec (all keys optional):
{
  "output": "shot.mp4",          # .mp4 opaque | .mov ProRes 4444 alpha | .webm VP9 alpha | .png still
  "aspect": "16:9",              # 16:9 | 9:16 | 1:1 | 4:5
  "quality": "draft",            # preview (25%, 8 spp) | draft (50%, 16 spp) | final (100%, 64 spp)
  "duration": 3.0, "fps": 30,
  "subject": {"type": "primitive", "shape": "cube"},
     # {"type":"model","path":"phone.glb"}
     # {"type":"image","path":"screenshot.png","thickness":0.04}
     # {"type":"text","text":"الدرس الأول","font":"fonts/Tajawal-ExtraBold.ttf"}
     # {"type":"text3d","text":"STEP 1"}
  "color": "#4C7DFF",            # subject color (primitive, text, text3d)
  "background": "#101418",       # hex or "transparent"
  "floor": true,
  "lighting": "studio",          # studio | soft | dramatic | neon
  "view": "standard",            # standard (exact colors) | agx (soft, photographic)
  "camera": {"move": "orbit", "angle": "eye", "lens": 50, "degrees": 60,
             "start_azimuth": -30, "ease": "ease_in_out", "dof": false, "fstop": 2.8,
             "shake": 0.0, "distance": null}
}
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

try:
    import bpy
    from mathutils import Euler, Quaternion, Vector
except ImportError:
    sys.exit("Blender's Python module is missing. Install it (needs Python 3.13 for bpy 5.x):\n"
             "  python3.13 -m venv ~/.bpy && ~/.bpy/bin/pip install bpy\n"
             "then run this script with ~/.bpy/bin/python")

ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
QUALITY = {"preview": (25, 8), "draft": (50, 16), "final": (100, 64)}
ANGLES = {  # elevation degrees, roll degrees
    "eye": (4, 0), "low": (-10, 0), "high": (28, 0), "birds_eye": (70, 0),
    "overhead": (88, 0), "dutch": (6, 12),
}
MOVES = ["static", "orbit", "dolly_in", "dolly_out", "crane_up", "crane_down", "truck_left",
         "truck_right", "dolly_zoom", "push_in_slow", "arc"]
DEFAULTS = {
    "output": "shot.mp4", "aspect": "16:9", "quality": "draft", "duration": 3.0, "fps": 30,
    "subject": {"type": "primitive", "shape": "cube"}, "color": "#4C7DFF",
    "background": "#101418", "floor": True, "lighting": "studio",
    "camera": {"move": "orbit", "angle": "eye", "lens": 50, "degrees": 60, "start_azimuth": -30,
               "ease": "ease_in_out", "dof": False, "fstop": 2.8, "shake": 0.0, "distance": None},
}


# ---------------------------------------------------------------- helpers
def use_nodes(block):
    # node trees are always on from Blender 6; the flag only exists before that
    if hasattr(block, "use_nodes") and not block.use_nodes:
        block.use_nodes = True


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def ease(t, kind):
    if kind == "linear":
        return t
    if kind == "ease_in":
        return t * t * t
    if kind == "ease_out":
        return 1 - (1 - t) ** 3
    return t * t * (3 - 2 * t) if kind == "smooth" else (
        4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2)  # ease_in_out (cubic)


def merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def has_arabic(s):
    return any("؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ࣿ" or "ﭐ" <= ch <= "﻿"
               for ch in s)


def material(name, color=None, image=None, unlit=False, alpha_from_image=False, mask=False,
             roughness=0.35):
    m = bpy.data.materials.new(name)
    use_nodes(m)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if image is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = roughness
        nt.links.new(bsdf.outputs[0], out.inputs[0])
        return m
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image)
    tex.extension = "CLIP"
    if mask:  # white-on-black mask: color comes from `color`
        tex.image.colorspace_settings.name = "Non-Color"
    if unlit:
        shade = nt.nodes.new("ShaderNodeEmission")
        if mask:
            shade.inputs["Color"].default_value = (*color, 1)
        else:
            nt.links.new(tex.outputs["Color"], shade.inputs["Color"])
    else:
        shade = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(tex.outputs["Color"], shade.inputs["Base Color"])
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    fac = tex.outputs["Color"] if mask else tex.outputs["Alpha"]
    nt.links.new(fac, mix.inputs["Fac"])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(shade.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def image_card(path, height=2.0, thickness=0.0, unlit=True, mask=False, color=(1, 1, 1)):
    img = bpy.data.images.load(path)
    w, h = img.size
    width = height * w / max(h, 1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0), rotation=(math.radians(90), 0, 0))
    card = bpy.context.object
    card.scale = (width, height, 1)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    card.data.materials.append(material("card", color=color, image=path, unlit=unlit, mask=mask))
    if thickness > 0:  # a slab behind the card, like a device or a printed board
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, thickness / 2 + 0.002, 0))
        slab = bpy.context.object
        slab.scale = (width * 1.02, thickness, height * 1.02)
        bpy.ops.object.transform_apply(scale=True)
        mod = slab.modifiers.new("bevel", "BEVEL")
        mod.width = min(width, height) * 0.03
        mod.segments = 4
        slab.data.materials.append(material("slab", color=hex_rgb("#1c1f24"), roughness=0.25))
        return [card, slab]
    return [card]


def text_mask_png(text, font, out_png, px=220):
    """Shape any language with libass (via FFmpeg) into a white-on-black mask PNG."""
    fontdir = os.path.dirname(os.path.abspath(font)) if font and os.path.isfile(font) else "."
    family = os.path.splitext(os.path.basename(font))[0].split("-")[0] if font else "Sans"
    if font and os.path.isfile(font):
        r = subprocess.run(["fc-scan", "--format", "%{family[0]}", font], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            family = r.stdout.strip()
    lines = text.split("\n")
    W = int(px * 0.62 * max(len(l) for l in lines)) + px * 2
    H = int(px * 1.6 * len(lines)) + px
    ass = out_png + ".ass"
    body = "\\N".join(lines)
    with open(ass, "w", encoding="utf-8") as f:
        f.write(f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: T,{family},{px},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,-1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                f"Dialogue: 0,0:00:00.00,0:00:01.00,T,,0,0,0,,{body}\n")
    esc = lambda p: p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d=1",
                        "-vf", f"ass='{esc(ass)}':fontsdir='{esc(fontdir)}',format=gray",
                        "-frames:v", "1", out_png], capture_output=True, text=True)
    if r.returncode:
        sys.exit("text render failed: " + r.stderr)
    # trim empty margins
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", out_png, "-vf", "cropdetect=limit=8:round=2:skip=0",
                        "-f", "null", "-"], capture_output=True, text=True)
    crop = [l.split("crop=")[-1].strip() for l in r.stderr.splitlines() if "crop=" in l]
    if crop:
        cw, ch, cx, cy = map(int, crop[-1].split(":"))
        pad = px // 4
        tmp = out_png + ".tmp.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out_png, "-vf",
                        f"crop={cw}:{ch}:{cx}:{cy},pad={cw + 2 * pad}:{ch + 2 * pad}:{pad}:{pad}:black",
                        tmp], check=True)
        os.replace(tmp, out_png)
    return out_png


# ---------------------------------------------------------------- scene
def build_subject(spec, workdir):
    sub, color = spec["subject"], hex_rgb(spec["color"])
    kind = sub.get("type", "primitive")
    objs = []
    if kind == "primitive":
        shape = sub.get("shape", "cube")
        add = {"cube": lambda: bpy.ops.mesh.primitive_cube_add(size=1.6),
               "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32),
               "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=1.8, vertices=64),
               "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=1, depth=1.8, vertices=64),
               "torus": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.35),
               "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=2)}.get(shape)
        if not add:
            sys.exit(f"unknown shape {shape}")
        add()
        o = bpy.context.object
        if shape == "cube":
            m = o.modifiers.new("bevel", "BEVEL")
            m.width, m.segments = 0.08, 5
        if shape in ("sphere", "monkey", "torus", "cylinder", "cone"):
            bpy.ops.object.shade_smooth()
        if shape == "monkey":
            o.modifiers.new("sub", "SUBSURF").levels = 2
        o.data.materials.append(material("subject", color=color))
        objs = [o]
    elif kind == "model":
        path = sub["path"]
        ext = os.path.splitext(path)[1].lower()
        before = set(bpy.data.objects)
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == ".stl":
            bpy.ops.wm.stl_import(filepath=path)
        else:
            sys.exit(f"unsupported model type {ext}")
        objs = [o for o in bpy.data.objects if o not in before]
        if sub.get("recolor"):
            mat = material("subject", color=color)
            for o in objs:
                if o.type == "MESH":
                    o.data.materials.clear()
                    o.data.materials.append(mat)
    elif kind == "image":
        objs = image_card(sub["path"], thickness=float(sub.get("thickness", 0.0)),
                          unlit=sub.get("unlit", True))
    elif kind == "text":
        png = text_mask_png(sub["text"], sub.get("font"), os.path.join(workdir, "text_mask.png"))
        objs = image_card(png, height=float(sub.get("height", 1.0)), mask=True, color=color,
                          thickness=float(sub.get("thickness", 0.0)))
    elif kind == "text3d":
        if has_arabic(sub["text"]):
            sys.exit('text3d cannot shape Arabic; use {"type":"text"} (a flat text card) instead')
        bpy.ops.object.text_add()
        o = bpy.context.object
        o.data.body = sub["text"]
        o.data.align_x, o.data.align_y = "CENTER", "CENTER"
        o.data.extrude = float(sub.get("depth", 0.12))
        o.data.bevel_depth = 0.012
        o.data.bevel_resolution = 3
        if sub.get("font"):
            o.data.font = bpy.data.fonts.load(sub["font"])
        o.rotation_euler = (math.radians(90), 0, 0)
        o.data.materials.append(material("subject", color=color, roughness=0.25))
        bpy.ops.object.convert(target="MESH")
        objs = [bpy.context.object]
    else:
        sys.exit(f"unknown subject type {kind}")

    # normalize: fit into a ~2 unit box centered on the origin
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    if not pts:
        sys.exit("subject has no mesh")
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    size = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
    scale = 2.0 / max(size, 1e-6) if kind in ("model",) else 1.0
    pivot = bpy.data.objects.new("subject_root", None)
    bpy.context.scene.collection.objects.link(pivot)
    center = (lo + hi) / 2
    for o in objs:
        if o.parent is None:
            o.parent = pivot
    pivot.location = -center * scale
    pivot.scale = (scale,) * 3
    bpy.context.view_layer.update()
    half = (hi - lo) * scale / 2
    radius = half.length
    frame_r = (math.hypot(half.x, half.y), half.z)  # orbit-safe width, height
    return pivot, radius, -half.z, frame_r  # floor height = bottom of subject


def add_area(name, loc, target, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = energy, size, color
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def sph(az, el, dist):
    a, e = math.radians(az), math.radians(el)
    return Vector((dist * math.sin(a) * math.cos(e), -dist * math.cos(a) * math.cos(e), dist * math.sin(e)))


def build_lights(preset, r):
    L = max(r, 0.5) * 4
    k = (L / 5) ** 2
    if preset == "soft":
        add_area("key", sph(-20, 50, L), (0, 0, 0), 900 * k, L * 1.5)
        add_area("fill", sph(140, 20, L), (0, 0, 0), 250 * k, L)
        return 0.8
    if preset == "dramatic":
        add_area("key", sph(-80, 20, L), (0, 0, 0), 1400 * k, L * 0.3)
        add_area("rim", sph(150, 35, L), (0, 0, 0), 900 * k, L * 0.3)
        return 0.05
    if preset == "neon":
        add_area("pink", sph(-70, 15, L), (0, 0, 0), 1100 * k, L * 0.6, (1.0, 0.15, 0.6))
        add_area("cyan", sph(70, 15, L), (0, 0, 0), 1100 * k, L * 0.6, (0.1, 0.8, 1.0))
        add_area("top", sph(0, 80, L), (0, 0, 0), 200 * k, L)
        return 0.1
    add_area("key", sph(-40, 35, L), (0, 0, 0), 1000 * k, L * 0.8)  # studio three-point
    add_area("fill", sph(50, 15, L), (0, 0, 0), 300 * k, L)
    add_area("rim", sph(170, 40, L), (0, 0, 0), 700 * k, L * 0.5)
    return 0.35


def animate_camera(spec, r, floor_z, frames, frame_r):
    c = spec["camera"]
    W, H = ASPECTS[spec["aspect"]]
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = float(c["lens"])
    cam_data.sensor_fit = "AUTO"
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    target = bpy.data.objects.new("focus", None)
    bpy.context.scene.collection.objects.link(target)
    if c.get("dof"):
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = target
        cam_data.dof.aperture_fstop = float(c.get("fstop", 2.8))

    tan_big = 18.0 / cam_data.lens  # 36 mm sensor fitted to the longer side
    tan_small = tan_big * min(W, H) / max(W, H)
    tan_x, tan_z = (tan_big, tan_small) if W >= H else (tan_small, tan_big)
    fit = max(frame_r[0] / tan_x, frame_r[1] / tan_z)
    d0 = float(c["distance"]) if c.get("distance") else fit * float(c.get("margin", 1.3))
    el0, roll = ANGLES.get(c["angle"], ANGLES["eye"])
    az0 = float(c.get("start_azimuth", -30))
    move = c["move"]
    if move not in MOVES:
        sys.exit(f"unknown move {move}; choose from {MOVES}")
    rng = random.Random(7)
    phases = [rng.uniform(0, 6.28) for _ in range(6)]
    prev = None
    for f in range(frames):
        t = ease(f / max(frames - 1, 1), c.get("ease", "ease_in_out"))
        az, el, dist, lens, shift = az0, el0, d0, cam_data.lens, Vector((0, 0, 0))
        if move == "orbit":
            az = az0 + float(c.get("degrees", 60)) * t
        elif move == "dolly_in":
            dist = d0 * (1.35 - 0.55 * t)
        elif move == "dolly_out":
            dist = d0 * (0.8 + 0.55 * t)
        elif move == "push_in_slow":
            dist = d0 * (1.1 - 0.12 * t)
        elif move == "crane_up":
            el = el0 - 12 + 45 * t
        elif move == "crane_down":
            el = el0 + 33 - 45 * t
        elif move in ("truck_left", "truck_right"):
            sgn = -1 if move == "truck_left" else 1
            right = Vector((math.cos(math.radians(az0)), math.sin(math.radians(az0)), 0))
            shift = right * sgn * r * (1.2 * t - 0.6)
        elif move == "dolly_zoom":
            dist = d0 * (1.7 - 0.9 * t)
            lens = float(c["lens"]) * dist / d0
        elif move == "arc":
            az = az0 + 35 * t
            dist = d0 * (1.25 - 0.3 * t)
            el = el0 + 8 * (1 - t)
        pos = sph(az, el, dist) + shift
        pos.z = max(pos.z, floor_z + 0.08 * r)  # never under the floor
        look = shift.copy()
        sh = float(c.get("shake", 0.0))
        rl = roll
        if sh > 0:
            s = f / bpy.context.scene.render.fps
            jitter = Vector(tuple(math.sin(s * (1.7 + i) * 2.1 + phases[i]) for i in range(3)))
            pos += jitter * 0.012 * sh * dist
            rl += math.sin(s * 2.3 + phases[4]) * 0.8 * sh
        quat = (look - pos).to_track_quat("-Z", "Y") @ Quaternion((0, 0, 1), math.radians(rl))
        eul = quat.to_euler("XYZ", prev) if prev else quat.to_euler("XYZ")
        prev = eul
        cam.location, cam.rotation_euler = pos, eul
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
        if lens != cam_data.lens or move == "dolly_zoom":
            cam_data.lens = lens
            cam_data.keyframe_insert("lens", frame=f + 1)
        target.location = look
        if c.get("dof"):
            target.keyframe_insert("location", frame=f + 1)
    return cam


def setup(spec, workdir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    W, H = ASPECTS.get(spec["aspect"]) or sys.exit(f"aspect must be one of {list(ASPECTS)}")
    pct, spp = QUALITY.get(spec["quality"]) or sys.exit(f"quality must be one of {list(QUALITY)}")
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = spp
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = W, H, pct
    s.render.fps = int(spec["fps"])
    frames = max(1, round(float(spec["duration"]) * spec["fps"]))
    s.frame_start, s.frame_end = 1, frames
    # Standard keeps brand colors exact; AgX is softer and more photographic
    s.view_settings.view_transform = "AgX" if spec.get("view") == "agx" else "Standard"
    if spec["quality"] != "final":
        s.cycles.max_bounces, s.cycles.diffuse_bounces, s.cycles.glossy_bounces = 4, 2, 2
        s.cycles.transmission_bounces, s.cycles.transparent_max_bounces = 2, 4

    _, r, floor_z, frame_r = build_subject(spec, workdir)
    amb = build_lights(spec["lighting"], r)
    world = bpy.data.worlds.new("world")
    use_nodes(world)
    bg = world.node_tree.nodes["Background"]
    transparent = spec["background"] == "transparent"
    bg_rgb = (0.5, 0.5, 0.5) if transparent else hex_rgb(spec["background"])
    bg.inputs["Color"].default_value = (*bg_rgb, 1)
    bg.inputs["Strength"].default_value = 1.0 if not transparent else amb
    s.world = world
    s.render.film_transparent = transparent
    if spec["floor"]:
        bpy.ops.mesh.primitive_plane_add(size=max(r, 1) * 60, location=(0, 0, floor_z))
        fl = bpy.context.object
        if transparent:
            fl.is_shadow_catcher = True
        else:
            fl.data.materials.append(material("floor", color=tuple(min(1, c * 1.15 + 0.004) for c in bg_rgb),
                                              roughness=0.6))
    animate_camera(spec, r, floor_z, frames, frame_r)
    return frames, transparent


def render_frames(frame_list, outdir, transparent):
    s = bpy.context.scene
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    paths = []
    for i, f in enumerate(frame_list):
        s.frame_set(f)
        p = os.path.join(outdir, f"f_{i + 1:05d}.png")
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
        print(f"rendered frame {f} ({i + 1}/{len(frame_list)})", flush=True)
    return paths


def encode(outdir, output, fps, transparent):
    ext = os.path.splitext(output)[1].lower()
    src = ["-framerate", str(fps), "-i", os.path.join(outdir, "f_%05d.png")]
    if ext == ".mov":
        codec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le" if transparent else "yuv422p10le"]
    elif ext == ".webm":
        codec = ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30",
                 "-pix_fmt", "yuva420p" if transparent else "yuv420p"]
    else:
        if transparent:
            print("note: .mp4 cannot hold transparency; use .mov or .webm for alpha", file=sys.stderr)
        codec = ["-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-movflags", "+faststart"]
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + src + codec + [output], check=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    storyboard = 0
    if "--storyboard" in argv:
        i = argv.index("--storyboard")
        storyboard = int(argv[i + 1])
        del argv[i:i + 2]
    if not argv:
        sys.exit(__doc__)
    raw = argv[0]
    user = json.loads(raw) if raw.strip().startswith("{") else json.load(open(raw, encoding="utf-8"))
    spec = merge(DEFAULTS, user)
    if spec["background"] != "transparent":
        hex_rgb(spec["background"])
    work = tempfile.mkdtemp(prefix="shot_")
    try:
        frames, transparent = setup(spec, work)
        out = spec["output"]
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
        if storyboard or out.lower().endswith(".png"):
            n = max(storyboard, 1)
            picks = [1] if n == 1 and not storyboard else [
                round(1 + (frames - 1) * k / max(n - 1, 1)) for k in range(n)]
            paths = render_frames(picks, work, transparent)
            target = out if out.lower().endswith(".png") else os.path.splitext(out)[0] + "_storyboard.png"
            if len(paths) == 1:
                shutil.copy(paths[0], target)
            else:
                ins = sum((["-i", p] for p in paths), [])
                subprocess.run(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex",
                               f"hstack=inputs={len(paths)}", target], check=True)
            print(f"wrote {target}")
        else:
            sc = bpy.context.scene
            sc.render.image_settings.file_format = "PNG"
            sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
            sc.render.filepath = os.path.join(work, "f_#####")
            bpy.ops.render.render(animation=True)
            encode(work, out, spec["fps"], transparent)
            print(f"wrote {out} ({frames} frames)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
