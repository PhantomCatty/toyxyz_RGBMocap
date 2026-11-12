"""Re-encode a written skeleton FBX through Blender's FBX importer/exporter.

Runs inside the bundled Blender runtime (started by mocap/fbx_export.py).
Strict Autodesk FBX SDK consumers, such as Cascadeur, can reject the compact
direct writer's minimal Definitions/header layout; Blender's exporter writes
the conventional full structure while keeping the skeleton and take intact.
"""
import sys
from pathlib import Path


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 2:
        raise SystemExit('usage: blender --background --python fbx_blender_pass.py -- <source.fbx> <target.fbx>')
    source, target = Path(args[0]), Path(args[1])
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.preferences.addon_enable(module='io_scene_fbx')
    except RuntimeError:
        pass  # Bundled add-on is enabled by default; import will fail clearly.
    bpy.ops.import_scene.fbx(filepath=str(source))
    scene = bpy.context.scene
    arms = [o for o in scene.objects if o.type == 'ARMATURE']
    if not arms:
        raise SystemExit('FBX re-encode found no armature in ' + source.name)
    # Bake exactly over every imported take's keyframe range.
    for action in bpy.data.actions:
        first, last = action.frame_range
        scene.frame_start = min(scene.frame_start, int(first))
        scene.frame_end = max(scene.frame_end, int(last))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arms[0]
    # Explicit terminal markers already exist; do not add Blender leaf bones.
    bpy.ops.export_scene.fbx(filepath=str(target), use_selection=True, object_types={'ARMATURE'},
                             add_leaf_bones=False, bake_anim=True, bake_anim_use_all_bones=True,
                             bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                             bake_anim_simplify_factor=0., axis_forward='-Z', axis_up='Y',
                             apply_unit_scale=True, global_scale=1.0)
    print('FBXPASS written: ' + str(target))


main()
