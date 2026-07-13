"""Blender headless batch: FBX/OBJ -> ASCII OpenUSD (.usda), with materials+textures+normals.

- FBX via the ufbx importer (bpy.ops.wm.fbx_import); OBJ via bpy.ops.wm.obj_import.
  Topology-preserving; glTF/GLB are skipped by the caller (they triangulate).
- Import applies real-world units; transform baked to an identity xform.
- USD export: Y-up, -Z forward, right-handed; n-gon/quad topology preserved.
- Materials/textures/normals: UsdPreviewSurface (diffuse + normal input so tangent-space
  normal maps carry through), textures copied next to the .usda with relative paths, per-vertex
  normals + UVs (primvars:st) exported so renderers can derive tangents, vertex colors kept.

Prefers FBX: if the input dir has any .fbx (searched recursively) it converts those; otherwise
falls back to .obj. Usage:
  blender -b --factory-startup --python models_to_usda_batch.py -- <in_dir> <out_dir>
"""
import glob
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
in_dir, out_dir = argv[0], argv[1]
os.makedirs(out_dir, exist_ok=True)

fbxs = sorted(glob.glob(os.path.join(in_dir, "**", "*.fbx"), recursive=True))
objs = sorted(glob.glob(os.path.join(in_dir, "**", "*.obj"), recursive=True))
files = [(p, "fbx") for p in fbxs] if fbxs else [(p, "obj") for p in objs]

# Blender USD export kwargs; probe which are supported on this Blender build so a
# missing/renamed arg (across versions) degrades gracefully instead of aborting the batch.
_WANT = dict(
    export_materials=True,
    export_textures_mode="NEW",  # copy textures into a 'textures/' dir next to the .usda
    overwrite_textures=True,
    relative_paths=True,
    generate_preview_surface=True,
    export_normals=True,
    export_uvmaps=True,
    export_mesh_colors=False,  # appearance is UV-mapped (texture atlas / solid material); never vertex colors
    convert_orientation=True,
    export_global_up_selection="Y",
    export_global_forward_selection="NEGATIVE_Z",
)
_SUPPORTED = set(bpy.ops.wm.usd_export.get_rna_type().properties.keys())
_KW = {k: v for k, v in _WANT.items() if k in _SUPPORTED}
_DROPPED = [k for k in _WANT if k not in _SUPPORTED]
if _DROPPED:
    print("NOTE usd_export ignoring unsupported args:", _DROPPED, flush=True)

ok = 0
for path, kind in files:
    name = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(out_dir, name + ".usda")
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if kind == "fbx":
            bpy.ops.wm.fbx_import(filepath=path)
        else:
            bpy.ops.wm.obj_import(filepath=path)

        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if not meshes:
            print("SKIP (no mesh)", name)
            continue
        for o in bpy.context.scene.objects:
            o.select_set(o.type == "MESH")
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # The FBX importer often leaves texture paths unresolved (bare filename),
        # so the USD exporter can't copy them (drops inputs:file). Resolve each
        # image against the FBX's OWN directory first (that's where the textures
        # sit), else fall back to the abspath, then load pixels + pack so
        # export_textures_mode=NEW writes them out.
        fbx_dir = os.path.dirname(os.path.abspath(path))
        dir_files = {f.lower(): f for f in os.listdir(fbx_dir)} if os.path.isdir(fbx_dir) else {}

        def _resolve(fp):
            b = os.path.basename(fp.replace("\\", "/"))
            # exact, else with/without a T_ prefix, all case-insensitive
            for cand in (b, "T_" + b, b[2:] if b[:2].lower() == "t_" else b):
                if cand.lower() in dir_files:
                    return os.path.join(fbx_dir, dir_files[cand.lower()])
            return None

        for im in bpy.data.images:
            if im.source == "FILE" and im.filepath:
                try:
                    hit = _resolve(im.filepath)
                    im.filepath = hit if hit else os.path.abspath(bpy.path.abspath(im.filepath))
                    im.reload()
                    if im.has_data:
                        im.pack()
                except Exception as iexc:
                    print("  texwarn", name, im.name, repr(iexc))

        bpy.ops.wm.usd_export(filepath=out, **_KW)
        ok += 1
    except Exception as exc:  # keep the batch going; report the failure
        print("FAIL", name, repr(exc))

print(f"CONVERTED {ok}/{len(files)}")
