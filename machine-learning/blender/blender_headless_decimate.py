import argparse
import json
import time
from pathlib import Path
import bpy


def getArguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ratio", type=float, default=0.10)
    parser.add_argument("--save-blend-copy", action="store_true")
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return parser.parse_args(argv)


def clearScene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def importModel(path):
    ext = path.suffix.lower()
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise ValueError(f"Unsupported input format: {ext}")

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects imported")
    return meshes


def counts(meshes):
    return sum(len(o.data.vertices) for o in meshes), sum(len(o.data.polygons) for o in meshes)


def main():
    args = getArguments()
    inputPath = Path(args.input).resolve()
    outputPath = Path(args.output).resolve()

    if not 0.0 < args.ratio <= 1.0:
        raise ValueError("--ratio must be > 0 and <= 1")

    outputPath.parent.mkdir(parents=True, exist_ok=True)
    clearScene()

    print(f"Importing: {inputPath}")
    meshes = importModel(inputPath)
    beforeV, beforeF = counts(meshes)
    print(f"Before: {beforeV:,} vertices, {beforeF:,} faces")

    started = time.perf_counter()

    for index, obj in enumerate(meshes, 1):
        print(f"[{index}/{len(meshes)}] Decimating {obj.name} at ratio {args.ratio:.4f}")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        modifier = obj.modifiers.new(name="HeadlessDecimate", type="DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = args.ratio
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    afterV, afterF = counts(meshes)
    print(f"After: {afterV:,} vertices, {afterF:,} faces")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(outputPath), export_format="GLB", use_selection=True)

    if args.save_blend_copy:
        bpy.ops.wm.save_as_mainfile(filepath=str(outputPath.with_suffix(".blend")))

    stats = {
        "input": str(inputPath),
        "output": str(outputPath),
        "ratio": args.ratio,
        "verticesBefore": beforeV,
        "facesBefore": beforeF,
        "verticesAfter": afterV,
        "facesAfter": afterF,
        "minutes": (time.perf_counter() - started) / 60.0,
    }
    outputPath.with_name(outputPath.stem + "_decimation_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("Finished")


if __name__ == "__main__":
    main()
