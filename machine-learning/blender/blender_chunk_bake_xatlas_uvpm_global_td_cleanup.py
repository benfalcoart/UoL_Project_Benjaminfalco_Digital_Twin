"""
Photogrammetry chunking, xatlas chart generation, UVPackmaster packing, texture baking and GLB export.

The optional automatic texture planner performs a first UV analysis pass over every chunk, measures the maximum density each chunk can achieve, chooses one common target density, then selects a per-chunk texture size. After final packing, each chunk is uniformly scaled to the same measured global texel density before baking.
"""

import bpy
import gpu
import sys
import math
import json
import argparse
from pathlib import Path
from collections import defaultdict
import bmesh
import numpy as np
import xatlas


#Blender 5.2 requires explicit GPU initialization before GPU-dependent addons can load in background mode:
if bpy.app.background:
    try:
        gpu.init()
        print("Background GPU initialized")
    except Exception as ex:
        print(f"WARNING: Could not initialize Blender GPU module: {ex}")


#Read arguments passed after Blender's "--":
def getArguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk-size", type=float, default=5.0)
    parser.add_argument("--texture-size", type=int, default=4096)
    parser.add_argument("--margin", type=int, default=8)
    parser.add_argument("--weld-distance", type=float, default=0.0)
    parser.add_argument("--projection-distance", type=float, default=0.01)

    #Optional cleanup for photogrammetry enclosure/box triangles:
    parser.add_argument("--remove-large-triangles", action="store_true")
    parser.add_argument("--large-triangle-area-factor", type=float, default=100.0)
    parser.add_argument("--large-triangle-edge-ratio", type=float, default=0.10)
    parser.add_argument("--large-triangle-max-face-fraction", type=float, default=0.02)
    parser.add_argument("--cleanup-only", action="store_true")

    #UVPackmaster settings:
    parser.add_argument("--uvpm-heuristic-time", type=int, default=5)
    parser.add_argument("--analysis-heuristic-time", type=int, default=1)
    parser.add_argument("--uvpm-precision", type=int, default=500)

    #Optional global texel-density planning:
    parser.add_argument("--auto-texture-size", action="store_true")
    parser.add_argument("--min-texture-size", type=int, default=2048)
    parser.add_argument("--max-texture-size", type=int, default=8192)
    parser.add_argument("--texture-step", type=int, default=512)
    parser.add_argument("--target-texel-density", type=float, default=0.0)
    parser.add_argument("--density-safety", type=float, default=0.95)
    parser.add_argument("--no-ml-data", action="store_true")

    arguments = sys.argv

    if "--" in arguments:
        arguments = arguments[arguments.index("--") + 1:]
    else:
        arguments = []

    return parser.parse_args(arguments)


#Clear the Blender scene of the default cube, light and camera:
def clearScene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


#Import a supported mesh:
def importMesh(path):
    extension = path.suffix.lower()

    if extension in [".glb", ".gltf"]:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif extension == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif extension == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported mesh format: {extension}")

    meshes = [object for object in bpy.context.scene.objects if object.type == "MESH"]

    if not meshes:
        raise ValueError("No mesh objects found after import")

    return meshes


#Join all imported mesh objects into one source mesh:
def joinMeshes(meshes):
    bpy.ops.object.select_all(action="DESELECT")

    for object in meshes:
        object.select_set(True)

    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()

    source = bpy.context.view_layer.objects.active
    source.name = "BakeSource"

    #Bake object transforms into the mesh:
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    return source


#Remove absurdly large enclosure/box polygons before chunking, UV generation and ML topology export:
def removeOversizedTriangles(source, outputPath, areaFactor=100.0, edgeRatio=0.10, maxFaceFraction=0.02):
    mesh = source.data
    faceCount = len(mesh.polygons)
    vertexCount = len(mesh.vertices)

    if faceCount == 0 or vertexCount == 0:
        raise RuntimeError("Cannot clean an empty source mesh")

    positionsFlat = np.empty(vertexCount * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", positionsFlat)
    positions = positionsFlat.reshape((-1, 3))

    bboxMin = np.min(positions, axis=0)
    bboxMax = np.max(positions, axis=0)
    bboxDiagonal = float(np.linalg.norm(bboxMax - bboxMin))

    faceAreas = np.empty(faceCount, dtype=np.float64)

    try:
        mesh.polygons.foreach_get("area", faceAreas)
    except Exception:
        faceAreas = np.fromiter((float(polygon.area) for polygon in mesh.polygons), dtype=np.float64, count=faceCount)

    positiveAreas = faceAreas[faceAreas > 1e-16]

    if len(positiveAreas) == 0:
        raise RuntimeError("Source mesh has no positive-area polygons")

    medianArea = float(np.median(positiveAreas))
    totalArea = float(np.sum(positiveAreas))
    areaThreshold = medianArea * float(areaFactor)
    edgeThreshold = bboxDiagonal * float(edgeRatio)

    areaCandidates = np.flatnonzero(faceAreas > areaThreshold)
    removeIndices = []
    longestEdges = []

    for polygonIndex in areaCandidates:
        polygon = mesh.polygons[int(polygonIndex)]
        vertexIds = np.asarray(polygon.vertices[:], dtype=np.int32)

        if len(vertexIds) < 3:
            continue

        polygonPositions = positions[vertexIds]
        edgeVectors = np.roll(polygonPositions, -1, axis=0) - polygonPositions
        longestEdge = float(np.max(np.linalg.norm(edgeVectors, axis=1)))

        if longestEdge > edgeThreshold:
            removeIndices.append(int(polygonIndex))
            longestEdges.append(longestEdge)

    candidateCount = len(removeIndices)
    candidateFraction = candidateCount / faceCount
    candidateArea = float(np.sum(faceAreas[removeIndices])) if removeIndices else 0.0
    candidateAreaFraction = candidateArea / totalArea if totalArea > 0 else 0.0

    report = {
        "enabled": True,
        "facesBefore": faceCount,
        "verticesBefore": vertexCount,
        "boundingBoxMin": bboxMin.tolist(),
        "boundingBoxMax": bboxMax.tolist(),
        "boundingBoxDiagonal": bboxDiagonal,
        "medianFaceArea": medianArea,
        "totalSurfaceArea": totalArea,
        "areaFactor": float(areaFactor),
        "areaThreshold": areaThreshold,
        "edgeRatio": float(edgeRatio),
        "edgeThreshold": edgeThreshold,
        "maxFaceFraction": float(maxFaceFraction),
        "areaCandidates": int(len(areaCandidates)),
        "candidateFaces": candidateCount,
        "candidateFaceFraction": candidateFraction,
        "candidateSurfaceArea": candidateArea,
        "candidateSurfaceAreaFraction": candidateAreaFraction,
        "candidateLongestEdgeMin": float(min(longestEdges)) if longestEdges else 0.0,
        "candidateLongestEdgeMax": float(max(longestEdges)) if longestEdges else 0.0,
        "removed": False,
        "refused": False,
        "message": "",
    }

    print(f"Faces before cleanup: {faceCount}")
    print(f"Median face area: {medianArea:.8g}")
    print(f"Bounding-box diagonal: {bboxDiagonal:.6g}")
    print(f"Large-face area threshold: {areaThreshold:.8g} ({areaFactor:g}x median)")
    print(f"Large-edge threshold: {edgeThreshold:.6g} ({edgeRatio * 100:.1f}% of bbox diagonal)")
    print(f"Large area candidates: {len(areaCandidates)}")
    print(f"Faces matching both tests: {candidateCount}")

    if candidateCount:
        print(f"Candidate face fraction: {candidateFraction * 100:.4f}%")
        print(f"Candidate surface-area fraction: {candidateAreaFraction * 100:.2f}%")

    if candidateCount == 0:
        report["message"] = "No oversized enclosure faces matched both cleanup tests."
        print(report["message"])
    elif candidateFraction > maxFaceFraction:
        report["refused"] = True
        report["message"] = f"Cleanup refused: {candidateCount} faces ({candidateFraction * 100:.2f}%) exceeds the safety limit of {maxFaceFraction * 100:.2f}%."
        print(f"WARNING: {report['message']}")
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        facesToDelete = [bm.faces[index] for index in removeIndices if index < len(bm.faces)]
        bmesh.ops.delete(bm, geom=facesToDelete, context="FACES")

        looseVertices = [vertex for vertex in bm.verts if not vertex.link_faces]

        if looseVertices:
            bmesh.ops.delete(bm, geom=looseVertices, context="VERTS")

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        report["removed"] = True
        report["facesAfter"] = len(mesh.polygons)
        report["verticesAfter"] = len(mesh.vertices)
        report["removedFaces"] = faceCount - len(mesh.polygons)
        report["removedVertices"] = vertexCount - len(mesh.vertices)
        report["removedSurfaceAreaEstimate"] = candidateArea
        report["message"] = "Oversized enclosure faces removed."

        print(f"Removed faces: {report['removedFaces']}")
        print(f"Removed loose vertices: {report['removedVertices']}")
        print(f"Faces after cleanup: {report['facesAfter']}")

    reportPath = Path(outputPath) / "large_triangle_cleanup.json"

    with reportPath.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"Cleanup report written to: {reportPath}")
    return report


#Export a quick cleaned GLB for visual inspection without running UV analysis/baking:
def exportCleanupPreview(source, outputPath, inputStem):
    previewPath = Path(outputPath) / f"{inputStem}_cleaned_preview.glb"
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    bpy.ops.export_scene.gltf(filepath=str(previewPath), export_format="GLB", use_selection=True)
    print(f"Cleaned preview written to: {previewPath}")
    return previewPath


#Store stable source vertex/face IDs so UV data can be mapped back onto the original 3D topology:
def ensureSourceIds(source):
    mesh = source.data
    vertexAttribute = mesh.attributes.get("SourceVertexId")
    faceAttribute = mesh.attributes.get("SourceFaceId")

    if not vertexAttribute:
        vertexAttribute = mesh.attributes.new(name="SourceVertexId", type="INT", domain="POINT")

    if not faceAttribute:
        faceAttribute = mesh.attributes.new(name="SourceFaceId", type="INT", domain="FACE")

    vertexIds = np.arange(len(mesh.vertices), dtype=np.int32)
    faceIds = np.arange(len(mesh.polygons), dtype=np.int32)
    vertexAttribute.data.foreach_set("value", vertexIds)
    faceAttribute.data.foreach_set("value", faceIds)
    mesh.update()


#Export the topology of the complete joined source mesh before spatial chunking.
#This is the global graph used by ML to connect triangles even when their UVs are baked into different maps:
def exportGlobalMeshTopology(source, sortedChunks, outputPath):
    mesh = source.data
    mesh.calc_loop_triangles()
    triangleCount = len(mesh.loop_triangles)

    if triangleCount == 0:
        raise RuntimeError("Source mesh has no triangles for global topology export")

    vertexCount = len(mesh.vertices)
    faceCount = len(mesh.polygons)

    positions = np.empty(vertexCount * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", positions)
    positions = positions.reshape((-1, 3))

    triangleVertexIndices = np.empty(triangleCount * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", triangleVertexIndices)
    triangleVertexIndices = triangleVertexIndices.reshape((-1, 3))

    trianglePolygonIndices = np.empty(triangleCount, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", trianglePolygonIndices)

    sourceVertexAttribute = mesh.attributes.get("SourceVertexId")
    sourceFaceAttribute = mesh.attributes.get("SourceFaceId")

    sourceVertexIds = np.arange(vertexCount, dtype=np.int32)
    sourceFaceIds = np.arange(faceCount, dtype=np.int32)

    if sourceVertexAttribute and sourceVertexAttribute.domain == "POINT":
        sourceVertexAttribute.data.foreach_get("value", sourceVertexIds)

    if sourceFaceAttribute and sourceFaceAttribute.domain == "FACE":
        sourceFaceAttribute.data.foreach_get("value", sourceFaceIds)

    triangleSourceVertexIds = sourceVertexIds[triangleVertexIndices]
    triangleSourceFaceIds = sourceFaceIds[trianglePolygonIndices]

    p0 = positions[triangleVertexIndices[:, 0]]
    p1 = positions[triangleVertexIndices[:, 1]]
    p2 = positions[triangleVertexIndices[:, 2]]
    cross = np.cross(p1 - p0, p2 - p0)
    crossLength = np.linalg.norm(cross, axis=1)
    triangleSurfaceAreas = (crossLength * 0.5).astype(np.float32)
    triangleNormals = np.zeros_like(cross, dtype=np.float32)
    validNormals = crossLength > 1e-12
    triangleNormals[validNormals] = (cross[validNormals] / crossLength[validNormals, None]).astype(np.float32)

    polygonMaterialIndices = np.empty(faceCount, dtype=np.int32)
    mesh.polygons.foreach_get("material_index", polygonMaterialIndices)
    triangleMaterialIndices = polygonMaterialIndices[trianglePolygonIndices]

    #Record which output chunk owns each original polygon/triangle:
    polygonChunkIndices = np.full(faceCount, -1, dtype=np.int32)
    chunkNames = []
    chunkKeys = []

    for chunkIndex, (chunkKey, faceIndices) in enumerate(sortedChunks):
        chunkName = f"chunk_{chunkIndex:04d}_{chunkKey[0]}_{chunkKey[1]}_{chunkKey[2]}"
        chunkNames.append(chunkName)
        chunkKeys.append(chunkKey)
        polygonChunkIndices[np.asarray(faceIndices, dtype=np.int32)] = chunkIndex

    triangleChunkIndices = polygonChunkIndices[trianglePolygonIndices]

    #Build global triangle adjacency from shared source-mesh edges using NumPy.
    #This avoids a very large Python edge dictionary on dense photogrammetry meshes:
    triangleIds = np.arange(triangleCount, dtype=np.int32)
    edges = np.stack((
        triangleSourceVertexIds[:, [0, 1]],
        triangleSourceVertexIds[:, [1, 2]],
        triangleSourceVertexIds[:, [2, 0]]
    ), axis=1).reshape((-1, 2))
    edgeTriangleIds = np.repeat(triangleIds, 3)
    edges.sort(axis=1)

    order = np.lexsort((edges[:, 1], edges[:, 0]))
    sortedEdges = edges[order]
    sortedEdgeTriangles = edgeTriangleIds[order]

    edgeChanges = np.empty(len(sortedEdges), dtype=np.bool_)
    edgeChanges[0] = True
    edgeChanges[1:] = np.any(sortedEdges[1:] != sortedEdges[:-1], axis=1)
    groupStarts = np.flatnonzero(edgeChanges)
    groupEnds = np.append(groupStarts[1:], len(sortedEdges))
    groupSizes = groupEnds - groupStarts

    pairA = []
    pairB = []
    pairEdge = []

    #Vectorize the normal manifold case (exactly two triangles per shared edge):
    exactTwo = groupStarts[groupSizes == 2]

    if len(exactTwo):
        pairA.append(sortedEdgeTriangles[exactTwo])
        pairB.append(sortedEdgeTriangles[exactTwo + 1])
        pairEdge.append(sortedEdges[exactTwo])

    #Non-manifold edges are uncommon, so expand their triangle pairs explicitly:
    for start, end in zip(groupStarts[groupSizes > 2], groupEnds[groupSizes > 2]):
        groupTriangles = sortedEdgeTriangles[start:end]
        groupEdge = sortedEdges[start]

        for first in range(len(groupTriangles) - 1):
            for second in range(first + 1, len(groupTriangles)):
                pairA.append(np.asarray([groupTriangles[first]], dtype=np.int32))
                pairB.append(np.asarray([groupTriangles[second]], dtype=np.int32))
                pairEdge.append(np.asarray([groupEdge], dtype=np.int32))

    if pairA:
        adjacencyA = np.concatenate(pairA).astype(np.int32, copy=False)
        adjacencyB = np.concatenate(pairB).astype(np.int32, copy=False)
        adjacencyPairs = np.column_stack((adjacencyA, adjacencyB)).astype(np.int32, copy=False)
        adjacencySharedEdgeVertexIds = np.concatenate(pairEdge).astype(np.int32, copy=False)

        edgeP0 = positions[adjacencySharedEdgeVertexIds[:, 0]]
        edgeP1 = positions[adjacencySharedEdgeVertexIds[:, 1]]
        adjacencyEdgeLengths = np.linalg.norm(edgeP1 - edgeP0, axis=1).astype(np.float32)
        adjacencyNormalCosine = np.einsum("ij,ij->i", triangleNormals[adjacencyA], triangleNormals[adjacencyB]).clip(-1.0, 1.0).astype(np.float32)
        adjacencyAbsNormalCosine = np.abs(adjacencyNormalCosine).astype(np.float32)
        adjacencyCrossChunk = (triangleChunkIndices[adjacencyA] != triangleChunkIndices[adjacencyB])
        adjacencySameSourceFace = (triangleSourceFaceIds[adjacencyA] == triangleSourceFaceIds[adjacencyB])
    else:
        adjacencyPairs = np.empty((0, 2), dtype=np.int32)
        adjacencySharedEdgeVertexIds = np.empty((0, 2), dtype=np.int32)
        adjacencyEdgeLengths = np.empty(0, dtype=np.float32)
        adjacencyNormalCosine = np.empty(0, dtype=np.float32)
        adjacencyAbsNormalCosine = np.empty(0, dtype=np.float32)
        adjacencyCrossChunk = np.empty(0, dtype=np.bool_)
        adjacencySameSourceFace = np.empty(0, dtype=np.bool_)

    outputPath = Path(outputPath)
    npzPath = outputPath / "global_mesh_topology.npz"
    jsonPath = outputPath / "global_mesh_topology.json"

    np.savez_compressed(
        npzPath,
        format_version=np.asarray([2], dtype=np.int32),
        source_mesh_name=np.asarray(source.name),
        vertex_positions=positions.astype(np.float32),
        source_vertex_ids=sourceVertexIds.astype(np.int32),
        triangle_ids=triangleIds,
        triangle_source_vertex_ids=triangleSourceVertexIds.astype(np.int32),
        triangle_source_face_ids=triangleSourceFaceIds.astype(np.int32),
        triangle_source_polygon_indices=trianglePolygonIndices.astype(np.int32),
        triangle_material_indices=triangleMaterialIndices.astype(np.int32),
        triangle_normals=triangleNormals,
        triangle_surface_areas=triangleSurfaceAreas,
        triangle_chunk_indices=triangleChunkIndices.astype(np.int32),
        chunk_names=np.asarray(chunkNames),
        chunk_keys=np.asarray(chunkKeys, dtype=np.int32),
        adjacency_pairs=adjacencyPairs,
        adjacency_shared_edge_vertex_ids=adjacencySharedEdgeVertexIds,
        adjacency_edge_lengths=adjacencyEdgeLengths,
        adjacency_normal_cosine=adjacencyNormalCosine,
        adjacency_abs_normal_cosine=adjacencyAbsNormalCosine,
        adjacency_cross_chunk=adjacencyCrossChunk.astype(np.bool_),
        adjacency_same_source_face=adjacencySameSourceFace.astype(np.bool_)
    )

    crossChunkCount = int(np.count_nonzero(adjacencyCrossChunk))
    summary = {
        "formatVersion": 2,
        "sourceMesh": source.name,
        "vertexCount": int(vertexCount),
        "sourceFaceCount": int(faceCount),
        "triangleCount": int(triangleCount),
        "chunkCount": int(len(chunkNames)),
        "adjacencyCount": int(len(adjacencyPairs)),
        "crossChunkAdjacencyCount": crossChunkCount,
        "npz": npzPath.name,
        "purpose": "Global 3D triangle graph linking ML classifications across UV maps/chunks"
    }

    with jsonPath.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"Global ML topology: {triangleCount} triangles, {len(adjacencyPairs)} adjacency links")
    print(f"Cross-chunk adjacency links: {crossChunkCount}")
    print(f"Global topology written to: {npzPath}")

    #Most imported photogrammetry meshes are already triangles. Avoid a huge dictionary
    #for that common case: direct-map one-triangle faces and only dictionary-map n-gons.
    faceTriangleCounts = np.bincount(triangleSourceFaceIds, minlength=faceCount).astype(np.int32)
    singleTriangleByFace = np.full(faceCount, -1, dtype=np.int32)
    singleMask = faceTriangleCounts[triangleSourceFaceIds] == 1
    singleTriangleByFace[triangleSourceFaceIds[singleMask]] = triangleIds[singleMask]
    multiLookup = {}

    multiTriangleIds = triangleIds[~singleMask]

    for triangleId in multiTriangleIds:
        faceId = int(triangleSourceFaceIds[triangleId])
        vertexKey = tuple(sorted(int(value) for value in triangleSourceVertexIds[triangleId]))
        multiLookup[(faceId, vertexKey)] = int(triangleId)

    return {
        "face_triangle_counts": faceTriangleCounts,
        "single_triangle_by_face": singleTriangleByFace,
        "multi_lookup": multiLookup
    }


#Assign source faces to spatial chunks using face centres:
def buildChunkGroups(source, chunkSize):
    chunks = defaultdict(list)

    for polygon in source.data.polygons:
        center = polygon.center
        chunkX = math.floor(center.x / chunkSize)
        chunkY = math.floor(center.y / chunkSize)
        chunkZ = math.floor(center.z / chunkSize)
        chunks[(chunkX, chunkY, chunkZ)].append(polygon.index)

    return chunks


#Create a chunk by duplicating the source object and deleting unwanted faces:
def createChunk(source, faceIndices, name, copyMaterials=True):
    chunk = source.copy()
    chunk.data = source.data.copy()
    chunk.name = name
    bpy.context.collection.objects.link(chunk)

    if copyMaterials:
        for index, material in enumerate(chunk.data.materials):
            if material:
                chunk.data.materials[index] = material.copy()

    keepFaces = set(faceIndices)

    bpy.ops.object.select_all(action="DESELECT")
    chunk.select_set(True)
    bpy.context.view_layer.objects.active = chunk
    bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(chunk.data)

    for face in bm.faces:
        face.select = face.index not in keepFaces

    bmesh.update_edit_mesh(chunk.data)
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")

    return chunk


#Create an identical target mesh for the new UV layout:
def createBakeTargetMesh(sourceChunk):
    targetChunk = sourceChunk.copy()
    targetChunk.data = sourceChunk.data.copy()
    targetChunk.name = f"{sourceChunk.name}_Target"
    bpy.context.collection.objects.link(targetChunk)
    return targetChunk


#Optionally weld duplicate vertices before generating the new UV atlas:
def weldChunkGeometry(chunk, distance):
    if distance <= 0:
        return

    mesh = chunk.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    print(f"Weld distance: {distance}")
    print(f"Welded vertices: {before} -> {len(mesh.vertices)}")


#Generate UV charts using xatlas. UVPackmaster performs the final packing afterwards:
def unwrapChunkXatlas(chunk, textureSize):
    mesh = chunk.data
    bakeUvName = "BakeUV"
    mesh.calc_loop_triangles()

    vertices = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", vertices)
    vertices = vertices.reshape((-1, 3))

    triangleVertices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.uint32)
    mesh.loop_triangles.foreach_get("vertices", triangleVertices)
    triangleVertices = triangleVertices.reshape((-1, 3))

    triangleLoops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.uint32)
    mesh.loop_triangles.foreach_get("loops", triangleLoops)
    triangleLoops = triangleLoops.reshape((-1, 3))

    print(f"Running xatlas on {len(mesh.vertices)} vertices and {len(mesh.loop_triangles)} triangles")

    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices, triangleVertices)

    chartOptions = xatlas.ChartOptions()
    chartOptions.fix_winding = True

    packOptions = xatlas.PackOptions()
    packOptions.resolution = textureSize
    packOptions.padding = 0

    atlas.generate(chart_options=chartOptions, pack_options=packOptions)
    vmapping, indices, uvs = atlas[0]

    if len(indices) != len(triangleLoops):
        raise RuntimeError(f"xatlas returned {len(indices)} triangles for {len(triangleLoops)} input triangles")

    existingBakeUv = mesh.uv_layers.get(bakeUvName)

    if existingBakeUv:
        mesh.uv_layers.remove(existingBakeUv)

    bakeUv = mesh.uv_layers.new(name=bakeUvName)
    mesh.uv_layers.active = bakeUv
    mesh.uv_layers.active_index = len(mesh.uv_layers) - 1

    for layer in mesh.uv_layers:
        layer.active_render = False

    bakeUv.active_render = True

    #xatlas can duplicate vertices at chart seams. Write its UV vertices back to Blender loops:
    for triangleIndex, atlasTriangle in enumerate(indices):
        loopIds = triangleLoops[triangleIndex]

        for cornerIndex in range(3):
            uv = uvs[atlasTriangle[cornerIndex]]
            bakeUv.data[int(loopIds[cornerIndex])].uv = (float(uv[0]), float(uv[1]))

    print(f"xatlas charts: {atlas.get_mesh_chart_count(0)}")
    print(f"xatlas utilization before UVPackmaster: {atlas.utilization:.3f}")

    return bakeUvName


#Enable and import UVPackmaster 4 in a way that works with Blender 5.2 --factory-startup --background:
def importUvPackmaster():
    import importlib

    moduleName = "bl_ext.user_default.uvpackmaster4"

    #Under --factory-startup UVPackmaster is installed but not enabled.
    #Enabling it through Blender creates the AddonPreferences entry UVPM expects:
    if moduleName not in bpy.context.preferences.addons:
        print("Enabling UVPackmaster 4...")
        result = bpy.ops.preferences.addon_enable(module=moduleName)

        if "FINISHED" not in result:
            raise RuntimeError(f"Could not enable UVPackmaster 4: {result}")

    uvpm4 = importlib.import_module(moduleName)

    #UVPackmaster 4.1.2 defines PackOpType here:
    typesModule = importlib.import_module(f"{moduleName}.spipeline.engine.types")
    PackOpType = typesModule.PackOpType
    UvpmRetCode = typesModule.UvpmRetCode

    return uvpm4, PackOpType, UvpmRetCode


#Select all UVs in the active BakeUV layer:
def selectAllUvs(chunk):
    bpy.ops.object.select_all(action="DESELECT")
    chunk.select_set(True)
    bpy.context.view_layer.objects.active = chunk

    bakeUv = chunk.data.uv_layers.get("BakeUV")

    if not bakeUv:
        raise RuntimeError("BakeUV does not exist before UVPackmaster packing")

    chunk.data.uv_layers.active = bakeUv
    chunk.data.uv_layers.active_index = list(chunk.data.uv_layers).index(bakeUv)
    bakeUv.active_render = True

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    bm = bmesh.from_edit_mesh(chunk.data)

    #Blender 5.2 requires the UV selection state to be initialized before
    #using the new BMesh UV-selection helpers. Since every mesh face is
    #selected above, syncing from the mesh selects all UVs as well:
    bm.uv_select_sync_from_mesh(sticky_select_mode="DISABLED")

    if not bm.uv_select_sync_valid:
        bm.uv_select_sync_valid = True

    bm.uv_select_flush_mode(flush_down=True)
    bm.uv_select_sync_to_mesh()

    bmesh.update_edit_mesh(chunk.data, loop_triangles=False, destructive=False)


#Use UVPackmaster 4 to repack the xatlas islands without changing their seams:
def packWithUvPackmaster(chunk, textureSize, margin, heuristicTime, precision):
    uvpm4, PackOpType, UvpmRetCode = importUvPackmaster()
    selectAllUvs(chunk)

    print(f"UVPackmaster: {textureSize}px, {margin}px margin, {heuristicTime}s heuristic")

    try:
        bpy.ops.uvpackmaster4.reset_to_defaults()

        uvpm4Prefs = uvpm4.utils.get_prefs()
        uvpm4Props = uvpm4.utils.get_main_props(bpy.context)

        uvpm4Props.precision = precision
        uvpm4Props.pixel_margin_enable = True
        uvpm4Props.pixel_margin = margin
        uvpm4Props.pixel_border_margin_enable = True
        uvpm4Props.pixel_border_margin = margin
        uvpm4Props.pixel_margin_tex_size = textureSize

        #Equalize average texel density between the xatlas islands before packing:
        uvpm4Props.normalize_scale = True

        #Allow the packer to search multiple layouts for better coverage:
        uvpm4Props.heuristic_enable = heuristicTime > 0

        if heuristicTime > 0:
            uvpm4Props.heuristic_search_time = heuristicTime

        modeId = "pack.single_tile"
        packOpType = PackOpType.PACK.value()

        result = bpy.ops.uvpackmaster4.pack(mode_id=modeId, pack_op_type=packOpType)

        prefs = uvpm4.utils.get_prefs()
        retCode = int(prefs.engine_retcode)

        #UVPackmaster code 8 is WARNING, not a failed pack. The packing result is
        #still usable, so log it and continue. Only actual error return codes abort:
        if retCode == UvpmRetCode.WARNING:
            print("UVPackmaster completed with WARNING (return code 8); keeping the packed UVs")
        elif retCode != UvpmRetCode.SUCCESS:
            raise RuntimeError(f"UVPackmaster engine returned error code {retCode}")

        print(f"UVPackmaster pack result: {result}, engine return code: {retCode}")

    finally:
        if chunk.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")


#Calculate the total 3D surface area of a chunk:
def calculateSurfaceArea(chunk):
    return sum(polygon.area for polygon in chunk.data.polygons)


#Calculate total UV triangle area in normalized 0-1 UV space:
def calculateUvArea(chunk, uvName="BakeUV"):
    mesh = chunk.data
    uvLayer = mesh.uv_layers.get(uvName)

    if not uvLayer:
        return 0.0

    mesh.calc_loop_triangles()
    totalArea = 0.0

    for triangle in mesh.loop_triangles:
        uv0 = np.array(uvLayer.data[triangle.loops[0]].uv, dtype=np.float64)
        uv1 = np.array(uvLayer.data[triangle.loops[1]].uv, dtype=np.float64)
        uv2 = np.array(uvLayer.data[triangle.loops[2]].uv, dtype=np.float64)
        edgeA = uv1 - uv0
        edgeB = uv2 - uv0
        totalArea += abs(edgeA[0] * edgeB[1] - edgeA[1] * edgeB[0]) * 0.5

    return totalArea


#Calculate average texel density in pixels per Blender unit:
def calculateTexelDensity(chunk, textureSize):
    surfaceArea = calculateSurfaceArea(chunk)
    uvArea = calculateUvArea(chunk)

    if surfaceArea <= 0 or uvArea <= 0:
        return 0.0, surfaceArea, uvArea

    texelDensity = textureSize * math.sqrt(uvArea / surfaceArea)
    return texelDensity, surfaceArea, uvArea


#Uniformly scale an already-packed UV map so its measured average texel density matches the global target:
def scaleUvMapToTexelDensity(chunk, textureSize, targetDensity, uvName="BakeUV"):
    currentDensity, surfaceArea, uvArea = calculateTexelDensity(chunk, textureSize)

    if targetDensity <= 0 or currentDensity <= 0:
        return currentDensity

    scale = targetDensity / currentDensity

    if scale > 1.0001:
        print(f"WARNING: {chunk.name} cannot reach target density at {textureSize}px ({currentDensity:.2f} < {targetDensity:.2f} px/unit)")
        return currentDensity

    uvLayer = chunk.data.uv_layers.get(uvName)

    if not uvLayer:
        raise RuntimeError(f"Missing UV layer: {uvName}")

    #UVPackmaster has already packed the layout inside 0-1. Scaling toward the tile centre
    #keeps the result inside the tile while preserving island proportions and preventing overlap:
    for loopUv in uvLayer.data:
        u = float(loopUv.uv[0])
        v = float(loopUv.uv[1])
        loopUv.uv = (0.5 + (u - 0.5) * scale, 0.5 + (v - 0.5) * scale)

    finalDensity, _, _ = calculateTexelDensity(chunk, textureSize)
    print(f"Global texel-density scale: {scale:.6f}")
    print(f"Texel density after global match: {finalDensity:.2f} px/unit")
    return finalDensity


#Round an automatically selected texture dimension upward to a convenient step:
def roundTextureSize(value, minimum, maximum, step):
    value = max(minimum, min(maximum, value))
    rounded = int(math.ceil(value / step) * step)
    return max(minimum, min(maximum, rounded))


#Choose a common texel density and a per-chunk texture size:
def buildTexturePlan(analysisResults, args):
    if not analysisResults:
        raise RuntimeError("No chunks were available for texture planning")

    analysisSize = args.max_texture_size

    if args.target_texel_density > 0:
        targetDensity = args.target_texel_density
    else:
        maxDensities = [result["texelDensity"] for result in analysisResults if result["texelDensity"] > 0]

        if not maxDensities:
            raise RuntimeError("Could not calculate a valid automatic texel density")

        #Choose a density every chunk can actually achieve at the maximum texture size.
        #The safety factor leaves room for small differences caused by pixel padding and heuristic packing:
        targetDensity = min(maxDensities) * args.density_safety

    plan = []

    for result in analysisResults:
        baseDensity = result["texelDensity"]

        if baseDensity <= 0:
            chosenSize = args.min_texture_size
            estimatedDensity = 0.0
        else:
            requiredSize = result["analysisTextureSize"] * targetDensity / baseDensity
            chosenSize = roundTextureSize(requiredSize, args.min_texture_size, args.max_texture_size, args.texture_step)
            estimatedDensity = baseDensity * (chosenSize / result["analysisTextureSize"])

        entry = dict(result)
        entry["chosenTextureSize"] = chosenSize
        entry["estimatedTexelDensity"] = estimatedDensity
        plan.append(entry)

    return targetDensity, plan


#Disjoint-set helper used to rebuild exact UV islands from packed triangle UVs:
class DisjointSet:
    def __init__(self, count):
        self.parent = np.arange(count, dtype=np.int32)
        self.rank = np.zeros(count, dtype=np.int8)

    def find(self, value):
        root = value

        while self.parent[root] != root:
            root = int(self.parent[root])

        while self.parent[value] != value:
            nextValue = int(self.parent[value])
            self.parent[value] = root
            value = nextValue

        return root

    def union(self, a, b):
        rootA = self.find(a)
        rootB = self.find(b)

        if rootA == rootB:
            return

        if self.rank[rootA] < self.rank[rootB]:
            rootA, rootB = rootB, rootA

        self.parent[rootB] = rootA

        if self.rank[rootA] == self.rank[rootB]:
            self.rank[rootA] += 1


#Extract final UV geometry and 3D topology for ML sampling/smoothing:
def exportMlUvData(chunk, outputPath, textureSize, texelDensity, globalTriangleMap=None, uvName="BakeUV"):
    mesh = chunk.data
    uvLayer = mesh.uv_layers.get(uvName)

    if not uvLayer:
        raise RuntimeError(f"Missing UV layer for ML export: {uvName}")

    mesh.calc_loop_triangles()
    triangles = list(mesh.loop_triangles)
    triangleCount = len(triangles)

    if triangleCount == 0:
        raise RuntimeError(f"{chunk.name} has no triangles for ML export")

    triangleVertices = np.empty((triangleCount, 3), dtype=np.int32)
    trianglePolygonIds = np.empty(triangleCount, dtype=np.int32)
    triangleUvs = np.empty((triangleCount, 3, 2), dtype=np.float32)
    triangleNormals = np.empty((triangleCount, 3), dtype=np.float32)

    for triangleIndex, triangle in enumerate(triangles):
        triangleVertices[triangleIndex] = triangle.vertices
        trianglePolygonIds[triangleIndex] = triangle.polygon_index
        triangleNormals[triangleIndex] = triangle.normal

        for cornerIndex, loopIndex in enumerate(triangle.loops):
            uv = uvLayer.data[loopIndex].uv
            triangleUvs[triangleIndex, cornerIndex] = (float(uv[0]), float(uv[1]))

    #Keep only vertices actually referenced by this chunk while retaining stable IDs from the original joined mesh:
    usedVertexIds = np.unique(triangleVertices.reshape(-1))
    remap = np.full(len(mesh.vertices), -1, dtype=np.int32)
    remap[usedVertexIds] = np.arange(len(usedVertexIds), dtype=np.int32)
    compactTriangles = remap[triangleVertices]

    allPositions = np.empty((len(mesh.vertices), 3), dtype=np.float32)
    mesh.vertices.foreach_get("co", allPositions.reshape(-1))
    vertexPositions = allPositions[usedVertexIds]

    sourceVertexAttribute = mesh.attributes.get("SourceVertexId")
    sourceFaceAttribute = mesh.attributes.get("SourceFaceId")

    if sourceVertexAttribute and sourceVertexAttribute.domain == "POINT":
        allSourceVertexIds = np.empty(len(mesh.vertices), dtype=np.int32)
        sourceVertexAttribute.data.foreach_get("value", allSourceVertexIds)
        sourceVertexIds = allSourceVertexIds[usedVertexIds]
    else:
        sourceVertexIds = usedVertexIds.astype(np.int32, copy=True)

    if sourceFaceAttribute and sourceFaceAttribute.domain == "FACE":
        allSourceFaceIds = np.empty(len(mesh.polygons), dtype=np.int32)
        sourceFaceAttribute.data.foreach_get("value", allSourceFaceIds)
        triangleSourceFaceIds = allSourceFaceIds[trianglePolygonIds]
    else:
        triangleSourceFaceIds = trianglePolygonIds.astype(np.int32, copy=True)

    triangleSourceVertexIds = allSourceVertexIds[triangleVertices] if sourceVertexAttribute and sourceVertexAttribute.domain == "POINT" else triangleVertices.astype(np.int32, copy=True)
    triangleGlobalIds = np.full(triangleCount, -1, dtype=np.int32)

    if globalTriangleMap is not None:
        faceTriangleCounts = globalTriangleMap["face_triangle_counts"]
        singleTriangleByFace = globalTriangleMap["single_triangle_by_face"]
        multiLookup = globalTriangleMap["multi_lookup"]

        for triangleIndex in range(triangleCount):
            faceId = int(triangleSourceFaceIds[triangleIndex])

            if 0 <= faceId < len(faceTriangleCounts) and faceTriangleCounts[faceId] == 1:
                triangleGlobalIds[triangleIndex] = singleTriangleByFace[faceId]
            else:
                vertexKey = tuple(sorted(int(value) for value in triangleSourceVertexIds[triangleIndex]))
                triangleGlobalIds[triangleIndex] = multiLookup.get((faceId, vertexKey), -1)

        missingGlobalIds = int(np.count_nonzero(triangleGlobalIds < 0))

        if missingGlobalIds:
            print(f"WARNING: Could not map {missingGlobalIds} chunk triangles back to global triangle IDs")

    p0 = allPositions[triangleVertices[:, 0]]
    p1 = allPositions[triangleVertices[:, 1]]
    p2 = allPositions[triangleVertices[:, 2]]
    triangleSurfaceAreas = (np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) * 0.5).astype(np.float32)

    uvEdgeA = triangleUvs[:, 1] - triangleUvs[:, 0]
    uvEdgeB = triangleUvs[:, 2] - triangleUvs[:, 0]
    triangleUvAreas = (np.abs(uvEdgeA[:, 0] * uvEdgeB[:, 1] - uvEdgeA[:, 1] * uvEdgeB[:, 0]) * 0.5).astype(np.float32)

    #Rebuild UV islands from 3D edge connectivity + continuous UV coordinates:
    disjoint = DisjointSet(triangleCount)
    edgeMap = defaultdict(list)
    uvTolerance = 1e-6

    for triangleIndex in range(triangleCount):
        vertices = triangleVertices[triangleIndex]
        uvs = triangleUvs[triangleIndex]

        for cornerA, cornerB in ((0, 1), (1, 2), (2, 0)):
            vertexA = int(vertices[cornerA])
            vertexB = int(vertices[cornerB])
            uvA = uvs[cornerA]
            uvB = uvs[cornerB]
            edgeKey = (min(vertexA, vertexB), max(vertexA, vertexB))

            if vertexA == edgeKey[0]:
                orderedUvA, orderedUvB = uvA, uvB
            else:
                orderedUvA, orderedUvB = uvB, uvA

            for previousTriangle, previousUvA, previousUvB in edgeMap[edgeKey]:
                if np.max(np.abs(orderedUvA - previousUvA)) <= uvTolerance and np.max(np.abs(orderedUvB - previousUvB)) <= uvTolerance:
                    disjoint.union(triangleIndex, previousTriangle)

            edgeMap[edgeKey].append((triangleIndex, orderedUvA.copy(), orderedUvB.copy()))

    rootToIsland = {}
    triangleIslandIds = np.empty(triangleCount, dtype=np.int32)

    for triangleIndex in range(triangleCount):
        root = disjoint.find(triangleIndex)

        if root not in rootToIsland:
            rootToIsland[root] = len(rootToIsland)

        triangleIslandIds[triangleIndex] = rootToIsland[root]

    islandCount = len(rootToIsland)
    islandTriangleCounts = np.bincount(triangleIslandIds, minlength=islandCount).astype(np.int32)
    islandSurfaceAreas = np.bincount(triangleIslandIds, weights=triangleSurfaceAreas, minlength=islandCount).astype(np.float32)
    islandUvAreas = np.bincount(triangleIslandIds, weights=triangleUvAreas, minlength=islandCount).astype(np.float32)
    islandUvBounds = np.full((islandCount, 4), [np.inf, np.inf, -np.inf, -np.inf], dtype=np.float32)

    for triangleIndex in range(triangleCount):
        islandId = triangleIslandIds[triangleIndex]
        uvs = triangleUvs[triangleIndex]
        islandUvBounds[islandId, 0] = min(islandUvBounds[islandId, 0], float(np.min(uvs[:, 0])))
        islandUvBounds[islandId, 1] = min(islandUvBounds[islandId, 1], float(np.min(uvs[:, 1])))
        islandUvBounds[islandId, 2] = max(islandUvBounds[islandId, 2], float(np.max(uvs[:, 0])))
        islandUvBounds[islandId, 3] = max(islandUvBounds[islandId, 3], float(np.max(uvs[:, 1])))

    #Pixel coordinates use image convention: X right, Y down. UV V therefore becomes 1-V:
    trianglePixels = np.empty_like(triangleUvs, dtype=np.float32)
    trianglePixels[:, :, 0] = triangleUvs[:, :, 0] * (textureSize - 1)
    trianglePixels[:, :, 1] = (1.0 - triangleUvs[:, :, 1]) * (textureSize - 1)

    islandPixelBounds = np.empty_like(islandUvBounds, dtype=np.int32)
    islandPixelBounds[:, 0] = np.floor(islandUvBounds[:, 0] * (textureSize - 1)).astype(np.int32)
    islandPixelBounds[:, 1] = np.floor((1.0 - islandUvBounds[:, 3]) * (textureSize - 1)).astype(np.int32)
    islandPixelBounds[:, 2] = np.ceil(islandUvBounds[:, 2] * (textureSize - 1)).astype(np.int32)
    islandPixelBounds[:, 3] = np.ceil((1.0 - islandUvBounds[:, 1]) * (textureSize - 1)).astype(np.int32)
    islandPixelAreaEstimate = (islandUvAreas * float(textureSize * textureSize)).astype(np.float32)

    #Build physical 3D adjacency. UV seams become links between separate islands even if UVPM packed them far apart:
    triangleAdjacencyPairs = []
    triangleAdjacencyNormalCosine = []
    triangleAdjacencyAbsNormalCosine = []
    triangleAdjacencyUvSeam = []
    islandAdjacency = {}

    normalLengths = np.linalg.norm(triangleNormals, axis=1)
    validNormals = normalLengths > 1e-12
    triangleNormalsNormalized = triangleNormals.copy()
    triangleNormalsNormalized[validNormals] /= normalLengths[validNormals, None]

    for edgeKey, entries in edgeMap.items():
        if len(entries) < 2:
            continue

        vertexA, vertexB = edgeKey
        edgeLength = float(np.linalg.norm(allPositions[vertexB] - allPositions[vertexA]))

        for firstIndex in range(len(entries) - 1):
            for secondIndex in range(firstIndex + 1, len(entries)):
                triangleA = entries[firstIndex][0]
                triangleB = entries[secondIndex][0]
                islandA = int(triangleIslandIds[triangleA])
                islandB = int(triangleIslandIds[triangleB])
                cosine = float(np.clip(np.dot(triangleNormalsNormalized[triangleA], triangleNormalsNormalized[triangleB]), -1.0, 1.0))
                uvSeam = islandA != islandB

                triangleAdjacencyPairs.append((triangleA, triangleB))
                triangleAdjacencyNormalCosine.append(cosine)
                triangleAdjacencyAbsNormalCosine.append(abs(cosine))
                triangleAdjacencyUvSeam.append(uvSeam)

                if uvSeam:
                    islandPair = (min(islandA, islandB), max(islandA, islandB))
                    entry = islandAdjacency.setdefault(islandPair, [0, 0.0, 0.0])
                    entry[0] += 1
                    entry[1] += edgeLength
                    entry[2] += abs(cosine) * edgeLength

    if triangleAdjacencyPairs:
        triangleAdjacencyPairs = np.asarray(triangleAdjacencyPairs, dtype=np.int32)
        triangleAdjacencyNormalCosine = np.asarray(triangleAdjacencyNormalCosine, dtype=np.float32)
        triangleAdjacencyAbsNormalCosine = np.asarray(triangleAdjacencyAbsNormalCosine, dtype=np.float32)
        triangleAdjacencyUvSeam = np.asarray(triangleAdjacencyUvSeam, dtype=np.bool_)
    else:
        triangleAdjacencyPairs = np.empty((0, 2), dtype=np.int32)
        triangleAdjacencyNormalCosine = np.empty(0, dtype=np.float32)
        triangleAdjacencyAbsNormalCosine = np.empty(0, dtype=np.float32)
        triangleAdjacencyUvSeam = np.empty(0, dtype=np.bool_)

    islandAdjacencyPairs = []
    islandAdjacencyEdgeCounts = []
    islandAdjacencyEdgeLengths = []
    islandAdjacencyAbsNormalCosine = []

    for islandPair, (edgeCount, edgeLength, weightedCosine) in sorted(islandAdjacency.items()):
        islandAdjacencyPairs.append(islandPair)
        islandAdjacencyEdgeCounts.append(edgeCount)
        islandAdjacencyEdgeLengths.append(edgeLength)
        islandAdjacencyAbsNormalCosine.append(weightedCosine / edgeLength if edgeLength > 0 else 0.0)

    if islandAdjacencyPairs:
        islandAdjacencyPairs = np.asarray(islandAdjacencyPairs, dtype=np.int32)
        islandAdjacencyEdgeCounts = np.asarray(islandAdjacencyEdgeCounts, dtype=np.int32)
        islandAdjacencyEdgeLengths = np.asarray(islandAdjacencyEdgeLengths, dtype=np.float32)
        islandAdjacencyAbsNormalCosine = np.asarray(islandAdjacencyAbsNormalCosine, dtype=np.float32)
    else:
        islandAdjacencyPairs = np.empty((0, 2), dtype=np.int32)
        islandAdjacencyEdgeCounts = np.empty(0, dtype=np.int32)
        islandAdjacencyEdgeLengths = np.empty(0, dtype=np.float32)
        islandAdjacencyAbsNormalCosine = np.empty(0, dtype=np.float32)

    outputPath = Path(outputPath)
    npzPath = outputPath / f"{chunk.name.replace('_Target', '')}_ml_uv.npz"
    jsonPath = outputPath / f"{chunk.name.replace('_Target', '')}_ml_uv.json"

    np.savez_compressed(
        npzPath,
        format_version=np.asarray([1], dtype=np.int32),
        chunk_name=np.asarray(chunk.name.replace("_Target", "")),
        texture_size=np.asarray([textureSize], dtype=np.int32),
        texel_density=np.asarray([texelDensity], dtype=np.float32),
        uv_name=np.asarray(uvName),
        pixel_mapping=np.asarray("x=u*(W-1), y=(1-v)*(H-1)"),
        vertex_positions=vertexPositions,
        source_vertex_ids=sourceVertexIds,
        triangles=compactTriangles,
        triangle_source_vertex_ids=triangleSourceVertexIds.astype(np.int32),
        triangle_source_face_ids=triangleSourceFaceIds,
        triangle_global_ids=triangleGlobalIds,
        triangle_uvs=triangleUvs,
        triangle_pixels=trianglePixels,
        triangle_island_ids=triangleIslandIds,
        triangle_normals=triangleNormalsNormalized.astype(np.float32),
        triangle_surface_areas=triangleSurfaceAreas,
        triangle_uv_areas=triangleUvAreas,
        island_triangle_counts=islandTriangleCounts,
        island_surface_areas=islandSurfaceAreas,
        island_uv_areas=islandUvAreas,
        island_pixel_area_estimate=islandPixelAreaEstimate,
        island_uv_bounds=islandUvBounds,
        island_pixel_bounds=islandPixelBounds,
        triangle_adjacency_pairs=triangleAdjacencyPairs,
        triangle_adjacency_normal_cosine=triangleAdjacencyNormalCosine,
        triangle_adjacency_abs_normal_cosine=triangleAdjacencyAbsNormalCosine,
        triangle_adjacency_uv_seam=triangleAdjacencyUvSeam,
        island_adjacency_pairs=islandAdjacencyPairs,
        island_adjacency_edge_counts=islandAdjacencyEdgeCounts,
        island_adjacency_edge_lengths=islandAdjacencyEdgeLengths,
        island_adjacency_abs_normal_cosine=islandAdjacencyAbsNormalCosine
    )

    summary = {
        "formatVersion": 1,
        "chunk": chunk.name.replace("_Target", ""),
        "textureSize": textureSize,
        "texelDensity": float(texelDensity),
        "uvLayer": uvName,
        "pixelMapping": "x=u*(W-1), y=(1-v)*(H-1)",
        "vertexCount": int(len(vertexPositions)),
        "triangleCount": int(triangleCount),
        "globalTriangleIdCount": int(np.count_nonzero(triangleGlobalIds >= 0)),
        "islandCount": int(islandCount),
        "triangleAdjacencyCount": int(len(triangleAdjacencyPairs)),
        "crossIslandAdjacencyCount": int(len(islandAdjacencyPairs)),
        "npz": npzPath.name
    }

    with jsonPath.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"ML UV data: {islandCount} islands, {len(islandAdjacencyPairs)} cross-island 3D links")
    print(f"ML UV sidecar: {npzPath.name}")

    return summary


#Create a bake image and material that receive the new texture:
def createBakeTarget(chunk, textureSize, texturePath):
    image = bpy.data.images.new(f"{chunk.name}_Texture", width=textureSize, height=textureSize, alpha=False)
    image.filepath_raw = str(texturePath)
    image.file_format = "PNG"
    image.colorspace_settings.name = "sRGB"

    material = bpy.data.materials.new(f"{chunk.name}_BakeTarget")
    material.use_nodes = True
    nodes = material.node_tree.nodes

    bakeTarget = nodes.new("ShaderNodeTexImage")
    bakeTarget.name = "BakeTarget"
    bakeTarget.image = image
    bakeTarget.select = True
    nodes.active = bakeTarget

    chunk.data.materials.clear()
    chunk.data.materials.append(material)

    for polygon in chunk.data.polygons:
        polygon.material_index = 0

    return image


#Prepare the original textured source for an emission bake:
def prepareEmissionSource(sourceChunk):
    if not sourceChunk.data.uv_layers:
        raise ValueError(f"{sourceChunk.name} has no original UV map")

    originalUvName = sourceChunk.data.uv_layers.active.name
    print(f"Source UV: {originalUvName}")

    for material in sourceChunk.data.materials:
        if not material:
            continue

        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        output = next((node for node in nodes if node.type == "OUTPUT_MATERIAL"), None)
        principled = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
        textureNodes = [node for node in nodes if node.type == "TEX_IMAGE" and node.image]

        if not textureNodes:
            print(f"WARNING: No source texture found in material: {material.name}")
            continue

        colorTextures = [node for node in textureNodes if node.image.colorspace_settings.name != "Non-Color"]
        colorTexture = colorTextures[0] if colorTextures else textureNodes[0]
        print(f"Using source texture: {colorTexture.image.name}")

        uvNode = nodes.new("ShaderNodeUVMap")
        uvNode.uv_map = originalUvName

        for textureNode in textureNodes:
            for link in list(textureNode.inputs["Vector"].links):
                links.remove(link)

            links.new(uvNode.outputs["UV"], textureNode.inputs["Vector"])

        sourceSocket = colorTexture.outputs["Color"]

        if principled:
            baseColor = principled.inputs["Base Color"]

            if baseColor.is_linked:
                sourceSocket = baseColor.links[0].from_socket

        if not output:
            output = nodes.new("ShaderNodeOutputMaterial")

        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Strength"].default_value = 1.0
        links.new(sourceSocket, emission.inputs["Color"])

        for link in list(output.inputs["Surface"].links):
            links.remove(link)

        links.new(emission.outputs["Emission"], output.inputs["Surface"])


#Bake the original textured source onto the xatlas/UVPackmaster target:
def bakeSourceToTarget(sourceChunk, targetChunk, image, margin, projectionDistance):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.margin = margin
    scene.render.bake.cage_extrusion = projectionDistance

    bpy.ops.object.select_all(action="DESELECT")
    sourceChunk.select_set(True)
    targetChunk.select_set(True)
    bpy.context.view_layer.objects.active = targetChunk

    bakeUv = targetChunk.data.uv_layers.get("BakeUV")

    if not bakeUv:
        raise RuntimeError("BakeUV does not exist on target")

    targetChunk.data.uv_layers.active = bakeUv
    targetChunk.data.uv_layers.active_index = list(targetChunk.data.uv_layers).index(bakeUv)
    bakeUv.active_render = True

    material = targetChunk.data.materials[0]
    nodes = material.node_tree.nodes
    bakeTarget = nodes.get("BakeTarget")

    for node in nodes:
        node.select = False

    bakeTarget.select = True
    nodes.active = bakeTarget

    print(f"Baking {sourceChunk.name} -> {targetChunk.name}")
    bpy.ops.object.bake(type="EMIT")
    image.save()


#Replace the temporary bake target material with a normal material using the baked texture:
def applyBakedMaterial(chunk, image):
    material = bpy.data.materials.new(f"{chunk.name}_BakedMaterial")
    material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    imageNode = nodes.new("ShaderNodeTexImage")
    uvNode = nodes.new("ShaderNodeUVMap")

    imageNode.image = image
    uvNode.uv_map = "BakeUV"
    links.new(uvNode.outputs["UV"], imageNode.inputs["Vector"])
    links.new(imageNode.outputs["Color"], principled.inputs["Base Color"])

    chunk.data.materials.clear()
    chunk.data.materials.append(material)

    for polygon in chunk.data.polygons:
        polygon.material_index = 0

    for uvLayer in list(chunk.data.uv_layers):
        if uvLayer.name != "BakeUV":
            chunk.data.uv_layers.remove(uvLayer)

    bakeUv = chunk.data.uv_layers.get("BakeUV")

    if bakeUv:
        chunk.data.uv_layers.active = bakeUv
        chunk.data.uv_layers.active_index = 0
        bakeUv.active_render = True


#Export one baked chunk:
def exportChunk(chunk, path):
    bpy.ops.object.select_all(action="DESELECT")
    chunk.select_set(True)
    bpy.context.view_layer.objects.active = chunk
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True)


#Remove a finished chunk from memory:
def removeChunk(chunk):
    mesh = chunk.data
    bpy.data.objects.remove(chunk, do_unlink=True)

    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)


#Run xatlas + UVPackmaster on a temporary target and measure its achievable texel density:
def analyzeChunk(source, faceIndices, chunkName, args):
    analysisSize = args.max_texture_size
    sourceChunk = createChunk(source, faceIndices, chunkName, copyMaterials=False)
    targetChunk = createBakeTargetMesh(sourceChunk)
    weldChunkGeometry(targetChunk, args.weld_distance)
    unwrapChunkXatlas(targetChunk, analysisSize)
    packWithUvPackmaster(targetChunk, analysisSize, args.margin, args.analysis_heuristic_time, args.uvpm_precision)

    texelDensity, surfaceArea, uvArea = calculateTexelDensity(targetChunk, analysisSize)

    result = {
        "name": chunkName,
        "faceCount": len(faceIndices),
        "surfaceArea": surfaceArea,
        "uvArea": uvArea,
        "utilization": uvArea,
        "analysisTextureSize": analysisSize,
        "texelDensity": texelDensity
    }

    print(f"Surface area: {surfaceArea:.4f}")
    print(f"UV coverage: {uvArea * 100:.2f}%")
    print(f"Maximum measured density at {analysisSize}px: {texelDensity:.2f} px/unit")

    removeChunk(targetChunk)
    removeChunk(sourceChunk)
    return result


#Bake and export one chunk using its planned texture size:
def bakeFinalChunk(source, faceIndices, chunkName, textureSize, args, targetDensity=0.0, globalTriangleMap=None):
    sourceChunk = createChunk(source, faceIndices, chunkName, copyMaterials=True)
    targetChunk = createBakeTargetMesh(sourceChunk)
    weldChunkGeometry(targetChunk, args.weld_distance)

    unwrapChunkXatlas(targetChunk, textureSize)
    packWithUvPackmaster(targetChunk, textureSize, args.margin, args.uvpm_heuristic_time, args.uvpm_precision)

    packedDensity, surfaceArea, packedUvArea = calculateTexelDensity(targetChunk, textureSize)
    print(f"Packed UV coverage: {packedUvArea * 100:.2f}%")
    print(f"Packed texel density: {packedDensity:.2f} px/unit")

    #Normalize Scale only guarantees equal density among islands in this one UVPM run.
    #For automatic sizing, match the entire packed chunk to the same global density used by every other chunk:
    finalDensity = packedDensity

    if targetDensity > 0:
        finalDensity = scaleUvMapToTexelDensity(targetChunk, textureSize, targetDensity)

    finalUvArea = calculateUvArea(targetChunk)
    print(f"Final UV coverage: {finalUvArea * 100:.2f}%")

    mlSummary = None

    if not args.no_ml_data:
        mlSummary = exportMlUvData(targetChunk, args.output, textureSize, finalDensity, globalTriangleMap)

    prepareEmissionSource(sourceChunk)

    texturePath = Path(args.output).resolve() / f"{chunkName}.png"
    image = createBakeTarget(targetChunk, textureSize, texturePath)
    bakeSourceToTarget(sourceChunk, targetChunk, image, args.margin, args.projection_distance)
    applyBakedMaterial(targetChunk, image)

    glbPath = Path(args.output).resolve() / f"{chunkName}.glb"
    exportChunk(targetChunk, glbPath)

    removeChunk(targetChunk)
    removeChunk(sourceChunk)

    return {
        "actualTextureSize": textureSize,
        "actualSurfaceArea": surfaceArea,
        "packedUvArea": packedUvArea,
        "actualUvArea": finalUvArea,
        "actualUtilization": finalUvArea,
        "packedTexelDensity": packedDensity,
        "actualTexelDensity": finalDensity,
        "mlUvData": mlSummary
    }


def main():
    args = getArguments()

    inputPath = Path(args.input).resolve()
    outputPath = Path(args.output).resolve()
    outputPath.mkdir(parents=True, exist_ok=True)

    print(f"Input: {inputPath}")
    print(f"Output: {outputPath}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Analysis/default texture size: {args.texture_size}")
    print(f"UV/bake margin: {args.margin}px")
    print(f"Weld distance: {args.weld_distance}")
    print(f"UVPackmaster final heuristic: {args.uvpm_heuristic_time}s")
    print(f"Automatic texture sizing: {args.auto_texture_size}")
    print(f"ML UV topology export: {not args.no_ml_data}")
    print(f"Large-triangle cleanup: {args.remove_large_triangles}")

    clearScene()
    meshes = importMesh(inputPath)
    source = joinMeshes(meshes)

    if args.remove_large_triangles:
        print("\n=== LARGE TRIANGLE CLEANUP ===")
        removeOversizedTriangles(source, outputPath, args.large_triangle_area_factor, args.large_triangle_edge_ratio, args.large_triangle_max_face_fraction)

    if args.cleanup_only:
        exportCleanupPreview(source, outputPath, inputPath.stem)
        print("Cleanup-only mode complete")
        return

    ensureSourceIds(source)

    print(f"Source vertices: {len(source.data.vertices)}")
    print(f"Source faces: {len(source.data.polygons)}")

    chunkGroups = buildChunkGroups(source, args.chunk_size)
    sortedChunks = list(sorted(chunkGroups.items()))
    print(f"Chunks: {len(sortedChunks)}")

    globalTriangleMap = None

    if not args.no_ml_data:
        print("\n=== GLOBAL ML TOPOLOGY ===")
        globalTriangleMap = exportGlobalMeshTopology(source, sortedChunks, outputPath)

    planByName = {}
    targetDensity = 0.0
    report = {
        "input": str(inputPath),
        "chunkSize": args.chunk_size,
        "margin": args.margin,
        "autoTextureSize": args.auto_texture_size,
        "chunks": []
    }

    if args.auto_texture_size:
        print("\n=== PASS 1: UV ANALYSIS ===")
        analysisResults = []

        for index, (chunkKey, faceIndices) in enumerate(sortedChunks):
            chunkName = f"chunk_{index:04d}_{chunkKey[0]}_{chunkKey[1]}_{chunkKey[2]}"
            print(f"\n[Analyze {index + 1}/{len(sortedChunks)}] {chunkName}")
            analysisResults.append(analyzeChunk(source, faceIndices, chunkName, args))

        targetDensity, texturePlan = buildTexturePlan(analysisResults, args)
        report["targetTexelDensity"] = targetDensity

        print("\n=== TEXTURE PLAN ===")
        print(f"Target texel density: {targetDensity:.2f} px/unit")

        for entry in texturePlan:
            planByName[entry["name"]] = entry
            difference = ((entry["estimatedTexelDensity"] / targetDensity) - 1.0) * 100 if targetDensity > 0 else 0.0
            print(f"{entry['name']}: {entry['chosenTextureSize']}px -> ~{entry['estimatedTexelDensity']:.2f} px/unit ({difference:+.1f}%)")
    else:
        for index, (chunkKey, faceIndices) in enumerate(sortedChunks):
            chunkName = f"chunk_{index:04d}_{chunkKey[0]}_{chunkKey[1]}_{chunkKey[2]}"
            planByName[chunkName] = {"name": chunkName, "chosenTextureSize": args.texture_size}

    print("\n=== PASS 2: FINAL PACK + BAKE ===")

    for index, (chunkKey, faceIndices) in enumerate(sortedChunks):
        chunkName = f"chunk_{index:04d}_{chunkKey[0]}_{chunkKey[1]}_{chunkKey[2]}"
        planEntry = planByName[chunkName]
        textureSize = int(planEntry["chosenTextureSize"])

        print(f"\n[Bake {index + 1}/{len(sortedChunks)}] {chunkName}")
        print(f"Faces: {len(faceIndices)}")
        print(f"Texture size: {textureSize}px")

        finalStats = bakeFinalChunk(source, faceIndices, chunkName, textureSize, args, targetDensity if args.auto_texture_size else 0.0, globalTriangleMap)
        planEntry.update(finalStats)
        report["chunks"].append(planEntry)

    reportPath = outputPath / "uv_texture_plan.json"

    with reportPath.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"\nTexture plan written to: {reportPath}")
    print("Chunking, UV packing and baking complete")


if __name__ == "__main__":
    main()
