"""Blender headless batch: FBX -> ASCII OpenUSD (.usda), verified conventions.

- new ufbx importer (bpy.ops.wm.fbx_import): applies FBX units + axis -> real-world meters
- bake the import transform into the mesh (identity xform, world-space meters)
- USD export: Y-up, -Z forward, right-handed; n-gon/quad topology preserved (no triangulation)

Usage: blender --background --factory-startup --python fbx_to_usda_batch.py -- <in_dir> <out_dir>
"""
import glob
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
in_dir, out_dir = argv[0], argv[1]
os.makedirs(out_dir, exist_ok=True)

fbxs = sorted(glob.glob(os.path.join(in_dir, "*.fbx")))
ok = 0
for path in fbxs:
    name = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(out_dir, name + ".usda")
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.fbx_import(filepath=path)

        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if not meshes:
            print("SKIP (no mesh)", name)
            continue
        for o in bpy.context.scene.objects:
            o.select_set(o.type == "MESH")
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        bpy.ops.wm.usd_export(
            filepath=out,
            export_materials=True,
            export_uvmaps=True,
            export_normals=True,
            convert_orientation=True,
            export_global_up_selection="Y",
            export_global_forward_selection="NEGATIVE_Z",
        )
        ok += 1
    except Exception as exc:  # keep the batch going; report the failure
        print("FAIL", name, repr(exc))

print(f"CONVERTED {ok}/{len(fbxs)}")
