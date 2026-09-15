"""Export the jig's hand stand-ins to Unity with the axis conversion BAKED into the vertices.

The whole scene exports as one FBX carrying both `HandR` and `HandL`, so the four stand-ins share a single
model asset and a shape change reaches all four through one reimport.

A mesh-only prop exported on the default recipe lands in Unity as a mesh node carrying a -90 deg X rotation.
Here that rotation would be a lie: each stand-in's node is a hold the author poses by hand, and a mesh that
arrives pre-rotated under it makes the frame in `Hands_build.py`'s docstring untrue of what you see in the
Scene view. `bake_space_transform` bakes the Blender->FBX axis change into the vertex data and leaves the
node at identity, which an armature-carrying avatar export must never do (it breaks bone-space) but a bare
mesh can. Unity's own bakeAxisConversion stays OFF on the importer.

Needs `vrc-blender-tools` on the path for its `export_unity_fbx`. Point `VRC_BLENDER_TOOLS` at that checkout;
absent it, this looks two levels above the package for a sibling clone, the ordinary workspace layout.

Run: VRC_BLENDER_TOOLS=<path> blender --background --factory-startup --python Hands_export.py -- <in.blend> <out.fbx>
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
print("AVATARPREP: export ->", export_unity_fbx(out_fbx, bake_space_transform=True))
