"""
This script will use the Blender topology files after all chunks of one reconstruction 
have been classified.
"""
import argparse
import csv
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from material_colors import MATERIAL_COLORS


def mapped_array(npz_path, name, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{name}.npy"

    if not destination.exists() or destination.stat().st_mtime < npz_path.stat().st_mtime:
        temporary = cache_dir / f"{name}.npy.tmp"
        with zipfile.ZipFile(npz_path) as archive, archive.open(f"{name}.npy") as source, temporary.open("wb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
        temporary.replace(destination)

    return np.load(destination, mmap_mode="r")



def load_results(topology_path, chunks_dir, results_dir, cache_dir):
    with np.load(topology_path) as source:
        names = [str(name) for name in source["chunk_names"]]
        triangle_count = len(source["triangle_chunk_indices"])

    source_vertices = mapped_array(topology_path, "triangle_source_vertex_ids", cache_dir)
    chunk_data = []
    total_nodes = 0

    for name in names:
        folder = results_dir / name

        with np.load(folder / "topology_segments.npz") as source:
            segments = source["segments"]

        with (folder / "topology_regions.json").open(encoding="utf-8") as file:
            manifest = json.load(file)

        if manifest["chunk_name"] != name:
            raise ValueError(f"Chunk metadata mismatch: {name}")

        chunk_data.append((name, segments, manifest, total_nodes))
        total_nodes += int(segments.max()) + 1

    labels = [""] * total_nodes
    confidence = np.zeros(total_nodes, dtype=np.float32)
    offsets = np.asarray([chunk[3] for chunk in chunk_data], dtype=np.int64)

    triangle_uv = np.lib.format.open_memmap(cache_dir / "aligned_triangle_uv.npy", mode="w+", dtype=np.float32, shape=(triangle_count, 3, 2))
    valid_uv = np.zeros(triangle_count, dtype=np.bool_)

    for name, segments, manifest, offset in chunk_data:
        for region in manifest["regions"]:
            node = offset + int(region["id"])
            labels[node] = region["material"]
            confidence[node] = float(region["confidence"])

        with np.load(chunks_dir / f"{name}_ml_uv.npz") as sidecar:
            global_ids = sidecar["triangle_global_ids"].astype(np.int64)
            local_vertices = sidecar["triangle_source_vertex_ids"].astype(np.int32)
            local_pixels = sidecar["triangle_pixels"].astype(np.float32)

        in_range = (global_ids >= 0) & (global_ids < triangle_count)
        ids = global_ids[in_range]
        vertices = local_vertices[in_range]
        pixels = local_pixels[in_range]

        expected = source_vertices[ids]
        matches = expected[:, :, None] == vertices[:, None, :]
        aligned = np.all(matches.sum(axis=2) == 1, axis=1)
        order = matches.argmax(axis=2)

        ids = ids[aligned]
        pixels = np.take_along_axis(pixels[aligned], order[aligned, :, None], axis=1)

        if len(np.unique(ids)) != len(ids) or np.any(valid_uv[ids]):
            raise ValueError(f"Duplicate global triangle IDs in {name}")

        triangle_uv[ids] = pixels
        valid_uv[ids] = True

        print(f"{name}: aligned {len(ids)} / {len(global_ids)} UV triangles")

    triangle_uv.flush()
    print(f"Aligned triangle coverage: {np.count_nonzero(valid_uv) / max(1, triangle_count):.2%}")

    return chunk_data, labels, confidence, triangle_uv, valid_uv, offsets


def sample_shared_edge(triangle_ids, shared_edges, source_vertices, triangle_uv, valid_uv, triangle_chunks, offsets, segment_maps, sample_count):
    count = len(triangle_ids)
    results = np.full((count, sample_count), -1, dtype=np.int64)

    if not count:
        return results

    vertices = source_vertices[triangle_ids]
    matches_a = vertices == shared_edges[:, 0, None]
    matches_b = vertices == shared_edges[:, 1, None]

    valid = valid_uv[triangle_ids] & (matches_a.sum(axis=1) == 1) & (matches_b.sum(axis=1) == 1)

    if not np.any(valid):
        return results

    valid_indices = np.flatnonzero(valid)
    ids = triangle_ids[valid]
    corners = triangle_uv[ids]

    ia = matches_a[valid].argmax(axis=1)
    ib = matches_b[valid].argmax(axis=1)
    ic = 3 - ia - ib

    rows = np.arange(len(ids))
    p0 = corners[rows, ia]
    p1 = corners[rows, ib]
    p2 = corners[rows, ic]

    edge = p1 - p0
    lengths = np.linalg.norm(edge, axis=1)

    altitudes = np.abs(edge[:, 0] * (p2[:, 1] - p0[:, 1]) - edge[:, 1] * (p2[:, 0] - p0[:, 0])) / np.maximum(lengths, 1e-7)
    inset = np.clip(0.8 / np.maximum(altitudes, 1e-7), 0.0001, 0.30)

    fractions = (np.arange(sample_count, dtype=np.float32) + 0.5) / sample_count

    base = p0[:, None, :] * (1.0 - fractions[None, :, None]) + p1[:, None, :] * fractions[None, :, None]
    samples = base * (1.0 - inset[:, None, None]) + p2[:, None, :] * inset[:, None, None]

    xs = np.rint(samples[:, :, 0]).astype(np.int32)
    ys = np.rint(samples[:, :, 1]).astype(np.int32)

    chunk_ids = triangle_chunks[ids]

    for chunk_id in np.unique(chunk_ids):
        if chunk_id < 0 or chunk_id >= len(segment_maps):
            continue

        selected = np.flatnonzero(chunk_ids == chunk_id)
        segments = segment_maps[int(chunk_id)]
        height, width = segments.shape

        px = xs[selected]
        py = ys[selected]

        inside = (px >= 0) & (px < width) & (py >= 0) & (py < height)

        local = np.zeros(px.shape, dtype=np.int32)
        local[inside] = segments[py[inside], px[inside]]

        node_ids = np.where(local > 0, offsets[int(chunk_id)] + local, -1)
        results[valid_indices[selected]] = node_ids

    return results



def build_neighbours(topology_path, triangle_uv, valid_uv, offsets, chunk_data, cache_dir, minimum_cosine=0.75, sample_count=5):
    pairs = mapped_array(topology_path, "adjacency_pairs", cache_dir)
    shared_edges = mapped_array(topology_path, "adjacency_shared_edge_vertex_ids", cache_dir)
    lengths = mapped_array(topology_path, "adjacency_edge_lengths", cache_dir)
    cosines = mapped_array(topology_path, "adjacency_normal_cosine", cache_dir)
    source_vertices = mapped_array(topology_path, "triangle_source_vertex_ids", cache_dir)
    triangle_chunks = mapped_array(topology_path, "triangle_chunk_indices", cache_dir)

    segment_maps = [chunk[1] for chunk in chunk_data]
    node_count = sum(int(chunk[1].max()) + 1 for chunk in chunk_data)
    aggregated = defaultdict(float)
    linked_samples = 0

    for start in range(0, len(pairs), 25_000):
        stop = min(start + 25_000, len(pairs))

        valid_edges = (cosines[start:stop] >= minimum_cosine) & (lengths[start:stop] > 0)

        if not np.any(valid_edges):
            continue

        edge_pairs = pairs[start:stop][valid_edges]
        edge_vertices = shared_edges[start:stop][valid_edges]

        left = sample_shared_edge(edge_pairs[:, 0], edge_vertices, source_vertices, triangle_uv, valid_uv, triangle_chunks, offsets, segment_maps, sample_count)
        right = sample_shared_edge(edge_pairs[:, 1], edge_vertices, source_vertices, triangle_uv, valid_uv, triangle_chunks, offsets, segment_maps, sample_count)

        weights = lengths[start:stop][valid_edges] * ((cosines[start:stop][valid_edges] - minimum_cosine) / (1.0 - minimum_cosine)) / sample_count

        good = (left >= 0) & (right >= 0) & (left != right)

        if not np.any(good):
            continue

        linked_samples += int(np.count_nonzero(good))

        a = np.minimum(left[good], right[good])
        b = np.maximum(left[good], right[good])

        sample_weights = np.broadcast_to(weights[:, None], left.shape)[good]
        keys = a * node_count + b

        unique, inverse = np.unique(keys, return_inverse=True)
        totals = np.bincount(inverse, weights=sample_weights)

        for key, weight in zip(unique, totals):
            aggregated[int(key)] += float(weight)

    graph = defaultdict(list)

    for key, weight in aggregated.items():
        a, b = divmod(key, node_count)
        graph[a].append((b, weight))
        graph[b].append((a, weight))

    print(f"Valid paired edge samples: {linked_samples}")
    print(f"Physical links between superpixels: {len(aggregated)}")

    return graph



def refine(labels, confidence, graph, agreement=0.80, protect_confidence=0.85):
    corrected = labels.copy()
    changes = []

    for node, neighbours in graph.items():
        if not labels[node] or confidence[node] >= protect_confidence or len(neighbours) < 2:
            continue

        support = defaultdict(float)
        for other, weight in neighbours:
            if labels[other]:
                support[labels[other]] += weight * max(0.1, float(confidence[other]))

        total = sum(support.values())
        if total <= 0:
            continue

        winning, strength = max(support.items(), key=lambda item: item[1])
        fraction = strength / total
        if winning != labels[node] and fraction >= agreement:
            corrected[node] = winning
            changes.append((node, labels[node], winning, float(confidence[node]), fraction))

    return corrected, changes


def write_results(chunk_data, labels, corrected, changes, results_dir):
    for name, segments, manifest, offset in chunk_data:
        colors = MATERIAL_COLORS
        palette = np.zeros((int(segments.max()) + 1, 4), dtype=np.uint8)

        for region in manifest["regions"]:
            local_id = int(region["id"])
            material = corrected[offset + local_id]
            palette[local_id, :3] = colors[material]
            palette[local_id, 3] = 255

        output = palette[segments]
        path = results_dir / name / "material_id_topology_refined.png"
        Image.fromarray(output, mode="RGBA").save(path)
        print("Saved:", path)

    with (results_dir / "topology_changes.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["global_segment_node", "old_material", "new_material", "original_confidence", "neighbour_agreement"])
        writer.writerows(changes)

    print("Topology corrections:", len(changes))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--chunks-dir", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--agreement", type=float, default=0.80)
    parser.add_argument("--protect-confidence", type=float, default=0.85)
    parser.add_argument("--edge-samples", type=int, default=5)
    parser.add_argument("--minimum-cosine", type=float, default=0.75)
    args = parser.parse_args()

    if args.edge_samples < 1 or not -1.0 < args.minimum_cosine < 1.0:
        parser.error("--edge-samples must be positive and --minimum-cosine must be between -1 and 1")

    cache_dir = args.results_dir / "_topology_cache"

    chunks, labels, confidence, triangle_uv, valid_uv, offsets = load_results(args.topology, args.chunks_dir, args.results_dir, cache_dir)
    graph = build_neighbours(args.topology, triangle_uv, valid_uv, offsets, chunks, cache_dir, args.minimum_cosine, args.edge_samples)

    corrected, changes = refine(labels, confidence, graph, args.agreement, args.protect_confidence)
    write_results(chunks, labels, corrected, changes, args.results_dir)

if __name__ == "__main__":
    main()
