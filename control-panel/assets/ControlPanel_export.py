"""Export the control panel to Unity: `ControlPanel.fbx`, the armature plus the one skinned mesh it deforms.

This is an armature export, so the axis conversion stays in the root node and `bake_space_transform` stays
off: baking it into the data is the bare-mesh route `absolute-grip-prop`'s `Hands_export.py` takes, and on a
rig it breaks bone space. Unity's own bakeAxisConversion stays OFF on the importer. The export is scoped to the
armature (`armature_obj`), which also strips texture paths: the material is made in Unity over the atlas PNGs.

The export mutates the opened scene (`export_unity_fbx` bakes object scale), so this opens the `.blend`, exports,
and never saves.

Needs `vrc-blender-tools` on the path for its `export_unity_fbx`. Point `VRC_BLENDER_TOOLS` at that checkout;
absent it, this looks two levels above the package for a sibling clone, the ordinary workspace layout.

Run: VRC_BLENDER_TOOLS=<path> blender --background --factory-startup --python ControlPanel_export.py -- <in.blend> <out.fbx>
"""
import os, sys, bpy

tools = os.environ.get("VRC_BLENDER_TOOLS")
if not tools:
    here = os.path.dirname(os.path.abspath(__file__))
    tools = os.path.normpath(os.path.join(here, "..", "..", "..", "vrc-blender-tools"))
if not os.path.isdir(tools):
    raise SystemExit(f"vrc-blender-tools not found at {tools}; set VRC_BLENDER_TOOLS to its checkout")
sys.path.insert(0, tools)
from avatarprep.core.fbx_export import export_unity_fbx
in_blend, out_fbx = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.open_mainfile(filepath=in_blend)
arm = bpy.data.objects["Armature"]
me = bpy.data.objects["ControlPanel"].data
print("AVATARPREP: export ->", export_unity_fbx(out_fbx, armature_obj=arm, bake_space_transform=False),
      f"bones={len(arm.data.bones)} verts={len(me.vertices)} faces={len(me.polygons)} "
      f"shapes={len(me.shape_keys.key_blocks) - 1}")
