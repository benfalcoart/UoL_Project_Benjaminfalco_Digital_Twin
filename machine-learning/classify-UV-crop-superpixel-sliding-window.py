"""
This is the MINC-2500 UV Superpixel Material Classification Test
with Sliding Window Verification.

It loads a ResNet18 model trained and fine-tuned using the MINC-2500 material dataset and applies it to 
a diffuse UV texture using a corresponding binary UV mask.

This script extends the UV superpixel classification approach by using SLIC (Simple Linear Iterative Clustering) 
superpixels to divide each UV island into visually coherent regions based on local image colour and spatial similarity.

Instead than dividing UV geometry using only rectangular spatial subdivision, the superpixel approach attempts to follow visible
material and texture boundaries within the UV texture.

A sliding-window verification stage is additionally used to investigate material clusters that disagree with their surrounding regions. This
provides a second source of classification evidence before small or ambiguous clusters are merged 
into neighbouring materials.

The classification pipeline:

1. Loads the diffuse UV texture and corresponding binary UV mask.

2. Finds individual connected UV islands within the texture mask. UV islands that are too small to provide useful classification
   samples are ignored.

3. Classifies each complete UV island to provide a parent material prediction that can be used as a fallback when individual
   superpixels cannot be classified reliably.

4. Determines an appropriate number of SLIC superpixels based on the total area of each UV island.

5. Uses SLIC segmentation to divide each UV island into visually coherent superpixel regions while restricting segmentation to valid UV geometry.

6. Extracts each superpixel using its original mask and UV coordinates.

7. Attempts to produce a clean rectangular classification sample from each superpixel:
   - The largest fully valid rectangular region is extracted.
   - Samples that are too small are rejected.
   - Optionally: the region is rotated when doing so produces a
     sufficiently larger valid classification crop.

8. Classifies valid superpixel samples using the trained MINC ResNet18 material classifier.

9. Uses the parent UV-island classification as a fallback for superpixels that are too small or irregular to provide a valid
   classification sample.

10. Applies optional neighbour smoothing to low-confidence superpixels. A low-confidence material prediction may be replaced when adjacent,
    higher-confidence superpixels show sufficient agreement on another material.

11. Groups adjacent superpixels with the same resolved material into coherent material clusters.

12. Identifies material clusters that disagree with neighbouring materials and may require additional verification.

13. Generates sliding classification windows across and around the disputed cluster.
    Windows with insufficient valid UV coverage are rejected.

14. Classifies each valid sliding window and measures its support for:
    - The cluster's currently assigned material.
    - The dominant material surrounding the cluster.

15. Reclassifies the cluster only when the surrounding material receives greater average support across the sliding windows.

16. Evaluates remaining small or fragmented material clusters using their shared boundaries
    with neighbouring clusters. Small low-confidence clusters may be reassigned when a sufficiently
    large proportion of their external boundary contacts another material.

17. Rebuilds the final material regions by combining adjacent superpixels that resolve to the same material.

18. Generates both:
    - A raw material ID map showing the individual superpixel results.
    - A merged material ID map showing the post-processed coherent material regions.

19. Generates boundary preview images for both the original SLIC superpixels and the final merged material regions.

20. Optionally saves the actual image crops supplied to the classifier for debugging and visual validation.

Purpose:

This script extends the earlier UV superpixel material classification method by introducing 
sliding-window verification as an additional classification stage.

SLIC superpixels provide image-aware segmentation that can follow local changes in colour and texture 
more effectively than geometry-only subdivision. However, individual superpixels and small groups of
superpixels may still produce incorrect or ambiguous classifications.

Neighbour smoothing and material-cluster merging use spatial context to reduce this noise, but relying 
entirely on neighbouring classifications can potentially remove a legitimate small material region.

Sliding-window verification provides additional image-based evidence before this occurs. Multiple overlapping
windows are sampled across the cluster and near its boundaries. Their ResNet predictions are used to
compare support for the cluster's current material against the dominant material surrounding it.

A disputed region is only reclassified when the surrounding material receives a sufficiently stronger average classification score. This
allows spatial context to influence the result while still requiring support from the trained material classifier.

The resulting classifications are written back into their original UV texture coordinates to create material ID maps for later use by the
digital twin pipeline.

The raw, verified, and post-processed results allow the effects of superpixel segmentation, spatial smoothing, sliding-window verification,
and coherent-region merging to be evaluated as separate stages of the classification pipeline.
"""

import os
import json
import cv2
import numpy as np
import torch
import torch.nn as nn
import argparse
import sys
import skimage
import hashlib
import sqlite3
import threading
import zlib
from pathlib import Path
from torchvision import transforms
from material_classifier import MaterialClassifier
from material_colors import MATERIAL_COLORS
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from skimage.segmentation import slic, mark_boundaries
from torchvision.models import resnet18, ResNet18_Weights



#Settings:
MIN_COMPONENT_AREA = 500

TARGET_SUPERPIXEL_AREA = 20000
MIN_SUPERPIXELS_PER_ISLAND = 4
MAX_SUPERPIXELS_PER_ISLAND = 160

CPU_WORKERS = 8
MIN_SLIC_ISLAND_AREA = 6000

SLIC_COMPACTNESS = 10.0
SLIC_SIGMA = 1.0

MIN_SUPERPIXEL_AREA = 1500
MIN_CLASSIFICATION_WIDTH = 64
MIN_CLASSIFICATION_HEIGHT = 64

ROTATION_IMPROVEMENT_THRESHOLD = 0.05
ENABLE_ROTATION = True

LOW_CONFIDENCE_THRESHOLD = 0.55
ENABLE_NEIGHBOR_SMOOTHING = True
NEIGHBOR_CONSENSUS_THRESHOLD = 0.67

MIN_COHERENT_REGION_SEGMENTS = 3
MIN_COHERENT_REGION_AREA = 60000
HIGH_CONFIDENCE_REGION_THRESHOLD = 0.90
MERGE_CONTACT_THRESHOLD = 0.60
MAX_REGION_MERGE_PASSES = 6

ENABLE_SLIDING_WINDOW_VERIFICATION = True
SLIDING_WINDOW_SIZE = 512
SLIDING_WINDOW_STRIDE = 256
MAX_SLIDING_WINDOWS_PER_CLUSTER = 12
SLIDING_VERIFY_AREA_THRESHOLD = 180000
SLIDING_VERIFY_CONFIDENCE_THRESHOLD = 0.85
SLIDING_VERIFY_CONTACT_THRESHOLD = 0.45
SLIDING_RECLASSIFY_MARGIN = 0.12
MIN_SLIDING_VALID_RATIO = 0.55

SAVE_DEBUG_CROPS = False

UV_CACHE_FORMAT_VERSION = 1


#Persistent, configuration-independent UV preprocessing cache.
#One SQLite database per chunk, shared by MINC/MatSynth/DMS and all voting modes.
class UVPreprocessCache:
    def __init__(self, path, diffuse_path, mask_path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._stats_lock = threading.Lock()
        self.stats = {"island_hits": 0, "island_misses": 0, "segmentation_hits": 0,
                      "segmentation_misses": 0, "crop_hits": 0, "crop_misses": 0}

        parameters = {
            "format": UV_CACHE_FORMAT_VERSION,
            "min_component_area": MIN_COMPONENT_AREA,
            "target_superpixel_area": TARGET_SUPERPIXEL_AREA,
            "min_superpixels": MIN_SUPERPIXELS_PER_ISLAND,
            "max_superpixels": MAX_SUPERPIXELS_PER_ISLAND,
            "min_slic_area": MIN_SLIC_ISLAND_AREA,
            "slic_compactness": SLIC_COMPACTNESS,
            "slic_sigma": SLIC_SIGMA,
            "min_width": MIN_CLASSIFICATION_WIDTH,
            "min_height": MIN_CLASSIFICATION_HEIGHT,
            "rotation_enabled": ENABLE_ROTATION,
            "rotation_improvement_threshold": ROTATION_IMPROVEMENT_THRESHOLD,
            "cv2": cv2.__version__,
            "skimage": skimage.__version__,
        }
        signature = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode("utf-8"))
        for input_path in (diffuse_path, mask_path):
            # Hash actual bytes, not timestamps: this rejects stale caches after any edit.
            with open(input_path, "rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    signature.update(block)
        self.signature = signature.hexdigest()

        db = self._connection()
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        previous = db.execute("SELECT value FROM metadata WHERE key = 'signature'").fetchone()
        if previous is None or previous[0] != self.signature:
            # All rows and crop samples were derived from an older texture, mask or algorithm.
            db.execute("DROP TABLE IF EXISTS islands")
            db.execute("DROP TABLE IF EXISTS crops")
            db.execute("DELETE FROM metadata")
            db.execute("INSERT INTO metadata (key, value) VALUES ('signature', ?)", (self.signature,))
            self.rebuilt = True
        else:
            self.rebuilt = False
        db.execute("CREATE TABLE IF NOT EXISTS islands (id INTEGER PRIMARY KEY, x INTEGER NOT NULL, y INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, area INTEGER NOT NULL, mask BLOB NOT NULL, segments BLOB)")
        db.execute("CREATE TABLE IF NOT EXISTS crops (key TEXT PRIMARY KEY, width INTEGER NOT NULL, height INTEGER NOT NULL, area INTEGER NOT NULL, rotated INTEGER NOT NULL, angle REAL NOT NULL, pixels BLOB)")
        db.commit()

    def _connection(self):
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(str(self.path), timeout=60)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=60000")
            db.execute("PRAGMA synchronous=NORMAL")
            self._local.db = db
        return db

    def _count(self, name, number=1):
        with self._stats_lock:
            self.stats[name] += number

    @staticmethod
    def _pack(array):
        return zlib.compress(np.ascontiguousarray(array).tobytes(), level=1)

    @staticmethod
    def _unpack(blob, dtype, shape):
        data = np.frombuffer(zlib.decompress(blob), dtype=dtype)
        if data.size != int(np.prod(shape)):
            raise ValueError("Cached UV array has unexpected dimensions")
        return data.reshape(shape).copy()

    def load_islands(self):
        db = self._connection()
        complete = db.execute("SELECT value FROM metadata WHERE key = 'islands_complete'").fetchone()
        if complete is None:
            return None
        rows = db.execute("SELECT id, x, y, width, height, area, mask FROM islands ORDER BY id").fetchall()
        if len(rows) != int(complete[0]) or any(row[0] != index for index, row in enumerate(rows)):
            return None
        try:
            islands = [{"x": x, "y": y, "width": w, "height": h, "area": area,
                        "mask": self._unpack(blob, np.uint8, (h, w))}
                       for _, x, y, w, h, area, blob in rows]
        except (ValueError, zlib.error):
            return None
        self._count("island_hits", len(islands))
        return islands

    def store_islands(self, islands):
        db = self._connection()
        # A transaction makes interrupted island discovery safely restartable.
        with db:
            db.execute("DELETE FROM islands")
            db.execute("DELETE FROM metadata WHERE key = 'islands_complete'")
            db.executemany("INSERT INTO islands (id,x,y,width,height,area,mask) VALUES (?,?,?,?,?,?,?)",
                           ((index, item["x"], item["y"], item["width"], item["height"], item["area"], self._pack(item["mask"]))
                            for index, item in enumerate(islands)))
            db.execute("INSERT INTO metadata (key,value) VALUES ('islands_complete',?)", (str(len(islands)),))
        self._count("island_misses", len(islands))

    def load_segments(self, index, island):
        row = self._connection().execute("SELECT segments FROM islands WHERE id=? AND x=? AND y=? AND width=? AND height=? AND area=?",
                                         (index, island["x"], island["y"], island["width"], island["height"], island["area"])).fetchone()
        if row is not None and row[0] is not None:
            try:
                segments = self._unpack(row[0], np.int32, (island["height"], island["width"]))
                self._count("segmentation_hits")
                return segments
            except (ValueError, zlib.error):
                pass
        self._count("segmentation_misses")
        return None

    def store_segments(self, index, segments):
        db = self._connection()
        with db:
            db.execute("UPDATE islands SET segments=? WHERE id=?", (self._pack(segments), index))

    def crop_key(self, image, mask):
        # Include the exact RGB crop and region mask to prevent false hits.
        digest = hashlib.sha256()
        digest.update(bytes(np.asarray(image.size, dtype=np.int32)))
        digest.update(image.convert("RGB").tobytes())
        digest.update(np.ascontiguousarray(mask, dtype=np.uint8).tobytes())
        return digest.hexdigest()

    def load_crop(self, key):
        row = self._connection().execute("SELECT width,height,area,rotated,angle,pixels FROM crops WHERE key=?", (key,)).fetchone()
        if row is None:
            self._count("crop_misses")
            return None
        w, h, area, rotated, angle, pixels = row
        try:
            image = Image.fromarray(self._unpack(pixels, np.uint8, (h, w, 3)), mode="RGB") if pixels is not None else None
        except (ValueError, zlib.error):
            self._count("crop_misses")
            return None
        self._count("crop_hits")
        return {"image": image, "area": int(area), "rotation_used": bool(rotated), "rotation_angle": float(angle)}

    def store_crop(self, key, prepared):
        image = prepared["image"]
        w, h = image.size if image is not None else (0, 0)
        pixels = self._pack(np.asarray(image.convert("RGB"), dtype=np.uint8)) if image is not None else None
        db = self._connection()
        with db:
            db.execute("INSERT OR REPLACE INTO crops (key,width,height,area,rotated,angle,pixels) VALUES (?,?,?,?,?,?,?)",
                       (key, int(w), int(h), int(prepared["area"]), int(prepared["rotation_used"]), float(prepared["rotation_angle"]), pixels))

    def print_summary(self):
        print("UV preprocessing cache:", self.path, flush=True)
        for name, count in self.stats.items():
            print(f"  {name}: {count}", flush=True)

    def close(self):
        db = getattr(self._local, "db", None)
        if db is not None:
            db.close()
            self._local.db = None

#Loads the trained material classification model and restores its class labels.
#TODO: Remove this? Responsiblity shifted to material classifer.
def load_model(model_path, device):
    checkpoint = torch.load(model_path, map_location=device, weights_only=True)

    classes = checkpoint["classes"]

    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    return model, classes

#Returns the smallest AABB (axis-aligned bounding box) containing all active mask pixels.
def tight_bounds(mask):
    ys, xs = np.where(mask > 0)

    if len(xs) == 0:
        return None

    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)

#Finds separate connected regions in the UV mask and ignores components that are too small 
#to provide a useful classification sample.
def get_connected_islands(mask):
    binary = (mask > 127).astype(np.uint8)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    islands = []

    for label_index in range(1, count):
        area = int(stats[label_index, cv2.CC_STAT_AREA])

        if area < MIN_COMPONENT_AREA:
            continue

        x = int(stats[label_index, cv2.CC_STAT_LEFT])

        y = int(stats[label_index, cv2.CC_STAT_TOP])

        width = int(stats[label_index, cv2.CC_STAT_WIDTH])

        height = int(stats[label_index, cv2.CC_STAT_HEIGHT])

        island_mask = (labels[y:y + height, x:x + width] == label_index).astype(np.uint8)

        islands.append(
            {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "area": area,
                "mask": island_mask
            }
        )

    return islands

#Finds the largest rectangular area contained within the valid mask.
#This reduces unused or invalid texture pixels in the classifier input.
def largest_valid_rectangle(mask):
    binary = (mask > 0).astype(np.uint8)

    height, width = binary.shape

    heights = np.zeros(width, dtype=np.int32)

    best_area = 0
    best_bounds = None

    for y in range(height):
        heights = np.where(binary[y] > 0, heights + 1, 0)

        stack = []

        for x in range(width + 1):
            current_height = (heights[x] if x < width else 0)

            start = x

            while stack and stack[-1][1] > current_height:
                index, bar_height = stack.pop()
                area = int(bar_height * (x - index))

                if area > best_area:
                    best_area = area

                    best_bounds = (index, y - bar_height + 1, x, y + 1)

                start = index

            if not stack or stack[-1][1] < current_height:
                stack.append((start, current_height))

    return best_bounds

#Rotates an image and its corresponding UV mask by the same angle, expands the output bounds, 
#and trims unused space around the result.
def rotate_image_and_mask(image, mask, angle):
    rgb = np.array(image.convert("RGB"))

    binary = (mask > 0).astype(np.uint8)

    height, width = binary.shape

    center = (width / 2.0, height / 2.0)

    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cosine = abs(matrix[0, 0])
    sine = abs(matrix[0, 1])

    new_width = max(1, int(height * sine + width * cosine))
    new_height = max(1, int(height * cosine + width * sine))

    matrix[0, 2] += (new_width / 2.0 - center[0])
    matrix[1, 2] += (new_height / 2.0 - center[1])

    rotated_image = cv2.warpAffine(rgb, matrix,(new_width, new_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    rotated_mask = cv2.warpAffine(binary, matrix,(new_width, new_height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    bounds = tight_bounds(rotated_mask)

    if bounds is None:
        return image, binary

    x1, y1, x2, y2 = bounds

    rotated_image = rotated_image[y1:y2, x1:x2]
    rotated_mask = rotated_mask[y1:y2, x1:x2]

    return (Image.fromarray(rotated_image), rotated_mask)

#Estimates the rotation angle that best aligns the UV region with an axis-aligned rectangular crop.
def get_best_rotation_angle(mask):
    binary = (mask > 0).astype(np.uint8)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return 0.0

    contour = max(contours, key=cv2.contourArea)

    rectangle = cv2.minAreaRect(contour)

    angle = float(rectangle[2])
    rect_width, rect_height = rectangle[1]

    if rect_width < rect_height:
        angle += 90.0

    return angle

#Extracts the largest fully valid rectangular texture region from a mask. Returns no classification 
#crop when the valid region is too small.
def crop_to_largest_valid_rectangle(image, mask):
    bounds = largest_valid_rectangle(mask)

    if bounds is None:
        return None, 0

    x1, y1, x2, y2 = bounds

    width = x2 - x1
    height = y2 - y1

    if width < MIN_CLASSIFICATION_WIDTH or height < MIN_CLASSIFICATION_HEIGHT:
        return None, 0

    cropped_image = image.crop((x1, y1, x2, y2))

    area = width * height

    return cropped_image, area

#Prepares a masked UV region for material classification by selecting the largest valid crop 
#and optionally rotating the region when doing so produces a sufficiently larger usable 
#classification area. Returns the prepared image along with crop area and rotation information.
def prepare_classification_image(image, mask):
    image_width, image_height = image.size
    mask_height, mask_width = mask.shape

    if image_width != mask_width or image_height != mask_height:
        raise ValueError(f"Image/mask size mismatch: image={image_width}x{image_height}, mask={mask_width}x{mask_height}")

    base_image, base_area = (crop_to_largest_valid_rectangle(image, mask))

    best_image = base_image
    best_area = base_area
    rotation_used = False
    rotation_angle = 0.0

    if ENABLE_ROTATION:
        angle = get_best_rotation_angle(mask)

        if abs(angle) >= 0.5:
            rotated_image, rotated_mask = (rotate_image_and_mask(image, mask, angle))

            rotated_crop, rotated_area = (crop_to_largest_valid_rectangle(rotated_image, rotated_mask))

            required_area = (base_area * (1.0 + ROTATION_IMPROVEMENT_THRESHOLD))

            if rotated_crop is not None and rotated_area >= required_area:
                best_image = rotated_crop
                best_area = rotated_area
                rotation_used = True
                rotation_angle = angle

    return {
        "image": best_image,
        "area": best_area,
        "rotation_used": rotation_used,
        "rotation_angle": rotation_angle
    }

#Classifies a prepared image using the trained material model and returns the highest probability 
#material predictions in descending order.
def classify_prepared_image(image, model, classes, transform, device, top_k=None):
    results, tied_materials = model.predict(image)

    if top_k is not None:
        results = results[:top_k]

    return results, tied_materials

#Prepares and classifies a masked UV region and returns both the material predictions and 
#information about the classification sample that was used.
def classify_region(image, mask, model, classes, transform, device, uv_cache=None):
    cache_key = uv_cache.crop_key(image, mask) if uv_cache is not None else None
    prepared = uv_cache.load_crop(cache_key) if uv_cache is not None else None
    if prepared is None:
        prepared = prepare_classification_image(image, mask)
        if uv_cache is not None:
            uv_cache.store_crop(cache_key, prepared)

    if prepared["image"] is None:
        return None

    #Get the results of the classification and any tied materials (for ensemble)
    results, tied_materials = classify_prepared_image(prepared["image"], model, classes, transform, device)

    return {
        "results": results,
        "tied_materials": tied_materials,
        "classification_image": prepared["image"],
        "classification_area": prepared["area"],
        "rotation_used": prepared["rotation_used"],
        "rotation_angle": prepared["rotation_angle"]
    }

#Determines the number of SLIC superpixels to generate based on the UV island area while enforcing 
#configured minimum and maximum limits.
def determine_superpixel_count(area):
    count = int(round(area / TARGET_SUPERPIXEL_AREA))

    return max(MIN_SUPERPIXELS_PER_ISLAND, min(count, MAX_SUPERPIXELS_PER_ISLAND))

#Divides a UV island into visually coherent regions using SLIC superpixel segmentation restricted 
#to the valid UV mask.
def create_superpixels(image, mask, n_segments):
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0

    valid = mask > 0

    segments = slic(rgb, n_segments=n_segments, compactness=SLIC_COMPACTNESS, sigma=SLIC_SIGMA, start_label=1, mask=valid, convert2lab=True, enforce_connectivity=True, channel_axis=-1)
    segments = np.where(valid, segments, 0).astype(np.int32)

    return segments

#Converts SLIC segment labels into individual masked superpixel regions while preserving their 
#positions in the original UV texture.
def build_superpixel_regions(island, island_image, segments):
    regions = []

    segment_ids = np.unique(segments)
    segment_ids = segment_ids[segment_ids > 0]

    for segment_id in segment_ids:
        local_mask = (segments == segment_id).astype(np.uint8)

        area = int(np.count_nonzero(local_mask))
        bounds = tight_bounds(local_mask)

        if bounds is None:
            continue

        x1, y1, x2, y2 = bounds

        region_image = island_image.crop((x1, y1, x2, y2))
        region_mask = local_mask[y1:y2, x1:x2]

        regions.append(
            {
                "segment_id": int(segment_id),
                "x": island["x"] + x1,
                "y": island["y"] + y1,
                "width": x2 - x1,
                "height": y2 - y1,
                "area": area,
                "mask": region_mask,
                "image": region_image,
                "results": None,
                "resolved_material": None,
                "resolved_confidence": 0.0,
                "fallback_used": False,
                "rotation_used": False,
                "rotation_angle": 0.0,
                "tied_materials": [],
            }
        )

    return regions

#Classifies each superpixel region using the trained material model. Regions that cannot provide a valid classification sample fall back
#to the parent UV-island prediction when one is available.
def classify_superpixel_regions(regions, parent_classification, model, classes, transform, device, uv_cache=None):
    parent_results = (parent_classification["results"] if parent_classification is not None else None)

    for region in regions:
        classification = None

        if region["area"] >= MIN_SUPERPIXEL_AREA:
            classification = classify_region(region["image"], region["mask"], model, classes, transform, device, uv_cache=uv_cache)

        if classification is None:
            if parent_results is None:
                region["resolved_material"] = "other"
                region["resolved_confidence"] = 0.0
                region["results"] = [("other", 0.0)]
                region["tied_materials"] = []
            else:
                region["resolved_material"] = (parent_results[0][0])
                region["resolved_confidence"] = (parent_results[0][1])
                region["results"] = parent_results
                region["tied_materials"] = parent_classification.get("tied_materials", [])

            region["fallback_used"] = True
            continue

        region["results"] = classification["results"]
        region["tied_materials"] = classification["tied_materials"]
        region["resolved_material"] = (classification["results"][0][0])
        region["resolved_confidence"] = (classification["results"][0][1])
        region["classification_image"] = (classification["classification_image"])
        region["classification_area"] = (classification["classification_area"])
        region["rotation_used"] = (classification["rotation_used"])
        region["rotation_angle"] = (classification["rotation_angle"])

#Builds a adjacency map describing which SLIC superpixels share horizontal or vertical boundaries with one another.
def get_segment_adjacency(segments):
    adjacency = {}

    segment_ids = np.unique(segments)

    for segment_id in segment_ids:
        if segment_id > 0:
            adjacency[int(segment_id)] = set()

    horizontal_a = segments[:, :-1]
    horizontal_b = segments[:, 1:]
    horizontal_changes = (horizontal_a != horizontal_b)

    pairs = np.stack((horizontal_a[horizontal_changes], horizontal_b[horizontal_changes]), axis=1)

    vertical_a = segments[:-1, :]
    vertical_b = segments[1:, :]
    vertical_changes = (vertical_a != vertical_b)

    vertical_pairs = np.stack(( vertical_a[vertical_changes], vertical_b[vertical_changes]), axis=1)

    all_pairs = np.concatenate((pairs, vertical_pairs), axis=0)

    for first, second in all_pairs:
        first = int(first)
        second = int(second)

        if first <= 0 or second <= 0 or first == second:
            continue

        adjacency.setdefault(first, set()).add(second)
        adjacency.setdefault(second, set()).add(first)

    return adjacency

#Re-evaluatesa any low-confidence superpixels using the material predictions of adjacent higher-confidence regions. 
#A prediction is replaced when neighbouring regions reach sufficient consensus.
def smooth_low_confidence_regions(regions, segments):
    if not ENABLE_NEIGHBOR_SMOOTHING:
        return

    by_id = {
        region["segment_id"]: region for region in regions
    }

    adjacency = get_segment_adjacency(segments)

    updates = []

    for region in regions:
        if region["resolved_confidence"] >= LOW_CONFIDENCE_THRESHOLD:
            continue

        neighbor_ids = adjacency.get(region["segment_id"],set())
        neighbor_materials = []

        for neighbor_id in neighbor_ids:
            neighbor = by_id.get(neighbor_id)

            if neighbor is None:
                continue

            if neighbor["resolved_confidence"] < LOW_CONFIDENCE_THRESHOLD:
                continue

            neighbor_materials.append(neighbor["resolved_material"])

        if len(neighbor_materials) < 2:
            continue

        counts = {}

        for material in neighbor_materials:
            counts[material] = (counts.get(material, 0) + 1)
        
        material = max(counts,key=counts.get)
        
        consensus = (counts[material]/ len(neighbor_materials))

        if consensus >= NEIGHBOR_CONSENSUS_THRESHOLD:
            updates.append((region, material, consensus))

    for region, material, consensus in updates:
        if region["resolved_material"] != material:
            region["tied_materials"] = []

        region["resolved_material"] = material
        region["neighbor_smoothed"] = True
        region["neighbor_consensus"] = consensus

#Counts the number of shared boundary pixels between each pair of adjacent superpixel regions.
def get_boundary_contact_counts(segments):
    contacts = {}

    def add_contacts(first_values, second_values):
        valid = ((first_values > 0) & (second_values > 0) & (first_values != second_values))

        first_values = first_values[valid]
        second_values = second_values[valid]

        for first, second in zip(first_values, second_values):
            first = int(first)
            second = int(second)

            key = (min(first, second), max(first, second))

            contacts[key] = (contacts.get(key, 0) + 1)

    add_contacts(segments[:, :-1], segments[:, 1:])
    add_contacts(segments[:-1, :], segments[1:, :])

    return contacts

#Groups connected superpixels with the same resolved material into coherent material clusters and calculates their combined area and confidence.
def build_material_clusters(regions, segments):
    by_id = {
        region["segment_id"]: region for region in regions
    }

    adjacency = get_segment_adjacency(segments)

    visited = set()
    clusters = []

    for region in regions:
        segment_id = region["segment_id"]

        if segment_id in visited:
            continue

        material = region["resolved_material"]

        stack = [segment_id]
        visited.add(segment_id)
        members = []

        while stack:
            current = stack.pop()
            current_region = by_id[current]
            members.append(current_region)

            for neighbor_id in adjacency.get(current, set()):
                if neighbor_id in visited:
                    continue

                neighbor = by_id.get(neighbor_id)

                if neighbor is None:
                    continue

                if neighbor["resolved_material"] != material:
                    continue

                visited.add(neighbor_id)
                stack.append(neighbor_id)

        total_area = sum(member["area"] for member in members)

        if total_area > 0:
            average_confidence = sum(member["resolved_confidence"] * member["area"] for member in members) / total_area
        else:
            average_confidence = 0.0

        clusters.append(
            {
                "material": material,
                "members": members,
                "segment_ids": {
                    member["segment_id"] for member in members
                },
                "area": total_area,
                "confidence": average_confidence
            }
        )

    return clusters


#Converts a ranked list of material predictions into a dictionary that allows probability values to be retrieved by material name.
def results_to_probability_dict(results):
    return {
        material: probability
        for material, probability in results
    }

#Measures how much of a material cluster's external boundary contacts each neighbouring material and returns the total external contact.
def get_cluster_external_contacts(cluster, segment_to_cluster, clusters, contacts):
    neighbor_contacts = {}
    total_external_contact = 0

    for (first_segment, second_segment), contact_count in contacts.items():
        first_cluster = segment_to_cluster.get(first_segment)

        second_cluster = segment_to_cluster.get(second_segment)

        if first_cluster is None or second_cluster is None or first_cluster == second_cluster:
            continue

        if first_segment in cluster["segment_ids"]:
            neighbor_index = second_cluster
        elif second_segment in cluster["segment_ids"]:
            neighbor_index = first_cluster
        else:
            continue

        neighbor_material = clusters[neighbor_index]["material"]
        neighbor_contacts[neighbor_material] = (neighbor_contacts.get(neighbor_material, 0) + contact_count)

        total_external_contact += contact_count

    return ( neighbor_contacts, total_external_contact)

#Creates a binary mask containing all superpixels that belong to a material cluster.
def get_cluster_mask(cluster, segments):
    return np.isin(segments, list(cluster["segment_ids"])).astype(np.uint8)

#Selects candidate sliding-window centers across a material cluster and near its boundary 
#while limiting the total number of samples.
def get_window_centers_for_cluster(cluster_mask, island_mask):
    bounds = tight_bounds(cluster_mask)

    if bounds is None:
        return []

    x1, y1, x2, y2 = bounds

    centers = [((x1 + x2) // 2,(y1 + y2) // 2)]

    for y in range(y1, y2, SLIDING_WINDOW_STRIDE):
        for x in range(x1, x2, SLIDING_WINDOW_STRIDE):
            sample_x = min(x, cluster_mask.shape[1] - 1)

            sample_y = min(y, cluster_mask.shape[0] - 1)

            if cluster_mask[sample_y, sample_x] > 0:
                centers.append((x, y))

    kernel = np.ones((5, 5), dtype=np.uint8)

    dilated = cv2.dilate(cluster_mask, kernel, iterations=1)

    boundary = ((dilated > 0) & (cluster_mask == 0) & (island_mask > 0))
    boundary_points = np.argwhere(boundary)

    if len(boundary_points) > 0:
        boundary_slots = max(1, MAX_SLIDING_WINDOWS_PER_CLUSTER // 2)

        step = max(1, len(boundary_points) // boundary_slots)

        for point in boundary_points[::step]:
            y, x = point

            centers.append((int(x), int(y)))

    unique = []
    seen = set()

    for x, y in centers:
        key = (int(x), int(y))

        if key in seen:
            continue

        seen.add(key)
        unique.append(key)

        if (len(unique) >= MAX_SLIDING_WINDOWS_PER_CLUSTER):
            break

    return unique

#Extracts and classifies a sliding window centered on the requested UV position. Windows with insufficient valid UV coverage are rejected.
def classify_sliding_window(island_image, island_mask, center_x, center_y, model, classes, transform, device, uv_cache=None):
    half = (SLIDING_WINDOW_SIZE // 2)

    width, height = (island_image.size)

    x1 = max(0, center_x - half)

    y1 = max(0, center_y - half)

    x2 = min(width, x1 + SLIDING_WINDOW_SIZE)

    y2 = min(height, y1 + SLIDING_WINDOW_SIZE)

    x1 = max(0, x2 - SLIDING_WINDOW_SIZE)

    y1 = max(0, y2 - SLIDING_WINDOW_SIZE)

    window_mask = island_mask[y1:y2, x1:x2]

    if window_mask.size == 0:
        return None

    valid_ratio = (np.count_nonzero(window_mask) / window_mask.size)

    if (valid_ratio < MIN_SLIDING_VALID_RATIO):
        return None

    window_image = island_image.crop((x1, y1, x2, y2))

    classification = classify_region(window_image, window_mask, model, classes, transform, device, uv_cache=uv_cache)

    if classification is None:
        return None

    return classification["results"]

# Verifies material clusters that disagree with their surrounding regions by comparing classification 
#support across multiple sliding windows. A cluster is reclassified only when the surrounding material 
#exceeds the current material by the configured support margin.
def verify_disagreement_clusters_with_sliding_windows(regions, segments, island_image, island_mask, model, classes, transform, device, uv_cache=None):
    if not ENABLE_SLIDING_WINDOW_VERIFICATION:
        return

    contacts = get_boundary_contact_counts(segments)

    clusters = build_material_clusters(regions, segments)

    segment_to_cluster = {}

    for cluster_index, cluster in enumerate(clusters):
        for segment_id in cluster["segment_ids"]:
            segment_to_cluster[segment_id] = cluster_index

    for cluster in clusters:
        (neighbor_contacts, total_external_contact) = get_cluster_external_contacts(cluster, segment_to_cluster, clusters, contacts)

        if total_external_contact == 0 or not neighbor_contacts:
            continue

        surrounding_material = max(neighbor_contacts,key=neighbor_contacts.get)

        if surrounding_material == cluster["material"]:
            continue

        surrounding_contact_ratio = (neighbor_contacts[surrounding_material] / total_external_contact)
        should_verify = (cluster["area"] <= SLIDING_VERIFY_AREA_THRESHOLD or cluster["confidence"] < SLIDING_VERIFY_CONFIDENCE_THRESHOLD or surrounding_contact_ratio >= SLIDING_VERIFY_CONTACT_THRESHOLD)

        if not should_verify:
            continue

        cluster_mask = get_cluster_mask(cluster, segments)
        centers = get_window_centers_for_cluster(cluster_mask, island_mask)

        if not centers:
            continue

        cluster_scores = []
        surrounding_scores = []

        used_windows = 0

        for center_x, center_y in centers:
            results = classify_sliding_window(island_image, island_mask, center_x, center_y, model, classes, transform, device, uv_cache=uv_cache)

            if results is None:
                continue

            probabilities = results_to_probability_dict(results)
            cluster_scores.append(probabilities.get(cluster["material"], 0.0))
            surrounding_scores.append(probabilities.get(surrounding_material, 0.0))
            used_windows += 1

        if used_windows == 0:
            continue

        cluster_support = (sum(cluster_scores) / used_windows)
        surrounding_support = (sum(surrounding_scores) / used_windows)
        support_margin = (surrounding_support - cluster_support)
        verified_material = (cluster["material"])

        if support_margin >= SLIDING_RECLASSIFY_MARGIN:
            verified_material = (surrounding_material)

        for member in cluster["members"]:
            member["sliding_verified"] = True
            member["sliding_window_count"] = used_windows
            member["sliding_cluster_support"] = cluster_support
            member["sliding_surrounding_support"] = surrounding_support

            if verified_material != cluster["material"]:
                member["tied_materials"] = []
                member["resolved_material"] = verified_material
                member["sliding_reclassified"] = True

#Merges small or fragmented material clusters into neighbouring materials when sufficient boundary contact supports the reassignment.
#High-confidence coherent regions are preserved when possible!
def merge_small_material_clusters(regions, segments):
    contacts = get_boundary_contact_counts(segments)

    for _ in range(MAX_REGION_MERGE_PASSES):
        clusters = build_material_clusters(regions, segments)

        segment_to_cluster = {}

        for cluster_index, cluster in enumerate(clusters):
            for segment_id in cluster["segment_ids"]:
                segment_to_cluster[segment_id] = cluster_index

        updates = []

        for cluster_index, cluster in enumerate(clusters):
            is_small = (len(cluster["members"]) < MIN_COHERENT_REGION_SEGMENTS or cluster["area"] < MIN_COHERENT_REGION_AREA)

            if not is_small:
                continue

            if cluster["confidence"] >= HIGH_CONFIDENCE_REGION_THRESHOLD and len(cluster["members"]) > 1:
                continue

            neighbor_contacts = {}
            total_external_contact = 0

            for (first_segment,second_segment), contact_count in contacts.items():
                first_cluster = segment_to_cluster.get(first_segment)
                second_cluster = segment_to_cluster.get(second_segment)

                if (first_cluster is None or second_cluster is None or first_cluster == second_cluster):
                    continue

                if first_cluster == cluster_index:
                    neighbor_index = second_cluster
                elif second_cluster == cluster_index:
                    neighbor_index = first_cluster
                else:
                    continue

                neighbor_material = clusters[neighbor_index]["material"]
                neighbor_contacts[neighbor_material] = (neighbor_contacts.get(neighbor_material,0) + contact_count)

                total_external_contact += contact_count

            if total_external_contact == 0 or not neighbor_contacts:
                continue

            target_material = max(neighbor_contacts, key=neighbor_contacts.get)
            contact_ratio = (neighbor_contacts[target_material] / total_external_contact)

            if contact_ratio < MERGE_CONTACT_THRESHOLD:
                continue

            if target_material == cluster["material"]:
                continue

            updates.append((cluster, target_material, contact_ratio))

        if not updates:
            break

        changed = False

        for cluster, target_material, contact_ratio in updates:
            for member in cluster["members"]:
                if member["resolved_material"] == target_material:
                    continue

                member["resolved_material"] = target_material
                member["tied_materials"] = []
                member["cluster_merged"] = True
                member["merge_contact_ratio"] = contact_ratio
                changed = True

        if not changed:
            break

#Combines adjacent superpixels with the same resolved material into final coherent material regions while preserving their UV coordinates.
def build_merged_regions(regions, segments, island):
    by_id = {
        region["segment_id"]: region for region in regions
    }

    adjacency = get_segment_adjacency(segments)

    visited = set()
    merged_regions = []

    for region in regions:
        start_id = region["segment_id"]

        if start_id in visited:
            continue

        material = region["resolved_material"]

        stack = [start_id]
        visited.add(start_id)
        member_ids = []

        while stack:
            current = stack.pop()
            member_ids.append(current)

            for neighbor_id in adjacency.get(current, set()):
                if neighbor_id in visited:
                    continue

                neighbor = by_id.get(neighbor_id)

                if neighbor is None:
                    continue

                if neighbor["resolved_material"] != material:
                    continue

                visited.add(neighbor_id)
                stack.append(neighbor_id)

        cluster_mask = np.isin(segments, member_ids).astype(np.uint8)

        bounds = tight_bounds(cluster_mask)

        if bounds is None:
            continue

        x1, y1, x2, y2 = bounds

        cropped_mask = cluster_mask[y1:y2, x1:x2]

        members = [ by_id[member_id] for member_id in member_ids]

        total_area = sum(member["area"] for member in members)

        if total_area > 0:
            confidence = sum(member["resolved_confidence"] * member["area"] for member in members) / total_area
        else:
            confidence = 0.0

        merged_regions.append(
            {
                "x": island["x"] + x1,
                "y": island["y"] + y1,
                "width": x2 - x1,
                "height": y2 - y1,
                "area": int(
                    np.count_nonzero(
                        cropped_mask
                    )
                ),
                "mask": cropped_mask,
                "resolved_material": material,
                "resolved_confidence": confidence,
                "segment_count": len(member_ids)
            }
        )

    return merged_regions

#Writes merged material regions into a label map using a unique integer label for each coherent region.
def add_merged_regions_to_label_map(merged_regions, full_label_map, next_label):
    for region in merged_regions:
        x = region["x"]
        y = region["y"]
        width = region["width"]
        height = region["height"]

        destination = full_label_map[y:y + height, x:x + width]

        mask = region["mask"] > 0
        destination[mask] = next_label
        next_label += 1

    return next_label

#Paints a masked material region into an RGBA output image using its assigned material color.
def paint_region(output, region, color):
    x = region["x"]
    y = region["y"]
    width = region["width"]
    height = region["height"]

    destination = output[y:y + height, x:x + width]

    mask = region["mask"] > 0

    destination[mask, 0] = color[0]
    destination[mask, 1] = color[1]
    destination[mask, 2] = color[2]
    destination[mask, 3] = 255

#Generates a colour-coded material ID map by writing each region's resolved material classification back into its original UV coordinates.
def generate_material_id_map(image_size, regions, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    width, height = image_size

    output = np.zeros((height, width, 4), dtype=np.uint8)

    for region in regions:
        material = region["resolved_material"]
        color = MATERIAL_COLORS.get(material,(255, 255, 255))
        paint_region(output, region, color)

    Image.fromarray(output, mode="RGBA").save(output_path)

#Use a pixel dithering design to display potential material ties when using ensembling.
def generate_tie_preview(regions, material_id_path, output_path):
    output = np.array(Image.open(material_id_path).convert("RGBA"), copy=True)

    for region in regions:
        tied = region.get("tied_materials", [])

        if len(tied) < 2 or region["resolved_material"] not in tied:
            continue

        x = int(region["x"])
        y = int(region["y"])
        width = int(region["width"])
        height = int(region["height"])

        destination = output[y:y + height, x:x + width]
        mask = region["mask"] > 0

        yy, xx = np.indices((height, width))
        pattern = (xx + x + yy + y) % len(tied)

        for index, material in enumerate(tied):
            selected = mask & (pattern == index)
            color = MATERIAL_COLORS.get(material, (255, 255, 255))

            destination[selected, :3] = color
            destination[selected, 3] = 255

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    Image.fromarray(output).save(output_path)


#Generates an RGBA preview showing region boundaries over the diffuse UV texture while keeping pixels outside the UV mask transparent.
def generate_superpixel_preview(diffuse, full_segment_map, full_mask, output_path):
    rgb = np.asarray(diffuse.convert("RGB"), dtype=np.float32) / 255.0

    preview = mark_boundaries(rgb, full_segment_map, color=(1.0, 0.0, 0.0), mode="thick")

    alpha = np.where(full_mask > 127, 255, 0).astype(np.uint8)

    rgba = np.zeros(( preview.shape[0],preview.shape[1],4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(preview * 255.0, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = alpha

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    Image.fromarray(rgba, mode="RGBA").save(output_path)

#Saves the final image crop used by the classifier for debugging and visual validation of the classification pipeline.
#Regions that did not produce their own classification crop are ignored.
#TODO: Give ignored regions their own color OR cluster them together for resampling?
def save_debug_crop(region, output_dir, index):
    if not SAVE_DEBUG_CROPS or "classification_image" not in region:
        return

    os.makedirs(output_dir, exist_ok=True)

    material = region["resolved_material"]
    confidence = int(region["resolved_confidence"] * 100)

    filename = f"superpixel_{index:03d}_{material}_{confidence}.png"
    path = os.path.join(output_dir, filename)

    region["classification_image"].save(path)

#Prepares one UV island using CPU operations only.
def prepare_island_for_ml(task):
    index, island, diffuse, uv_cache = task

    x = island["x"]
    y = island["y"]
    width = island["width"]
    height = island["height"]

    island_image = diffuse.crop((x, y, x + width, y + height))
    island_mask = island["mask"]

    segments = uv_cache.load_segments(index, island) if uv_cache is not None else None
    if segments is None:
        if island["area"] < MIN_SLIC_ISLAND_AREA:
            segments = (island_mask > 0).astype(np.int32)
        else:
            n_segments = determine_superpixel_count(island["area"])
            segments = create_superpixels(island_image, island_mask, n_segments)
        if uv_cache is not None:
            uv_cache.store_segments(index, segments)

    segment_ids = np.unique(segments)
    segment_ids = segment_ids[segment_ids > 0]

    regions = build_superpixel_regions(island, island_image, segments)

    return island_image, island_mask, segments, segment_ids, regions


#Keeps a small number of upcoming UV islands prepared in parallel.
def prepared_islands(islands, diffuse, uv_cache=None):
    with ThreadPoolExecutor(max_workers=CPU_WORKERS) as executor:
        jobs = ((index, island, diffuse, uv_cache) for index, island in enumerate(islands))
        if sys.version_info >= (3, 14):
            yield from executor.map(prepare_island_for_ml, jobs, buffersize=CPU_WORKERS)
        else:
            # Backport bounded mapping: don't queue thousands of large islands at once.
            from collections import deque
            pending = deque()
            for _ in range(CPU_WORKERS):
                task = next(jobs, None)
                if task is not None:
                    pending.append(executor.submit(prepare_island_for_ml, task))
            while pending:
                result = pending.popleft().result()
                task = next(jobs, None)
                if task is not None:
                    pending.append(executor.submit(prepare_island_for_ml, task))
                yield result

#Runs the complete superpixel-based UV material classification pipeline:
#loads the model and textures, generates and classifies SLIC superpixels,
#applies neighbour smoothing and sliding-window verification, merges coherent
#material regions, saves debug crops, and generates the final output maps.
def main():    
    base_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=["minc", "matsynth", "dms", "minc_legacy"], default=["minc"])
    parser.add_argument("--method", choices=["soft", "hard"], default="soft")
    parser.add_argument("--tie-tolerance", type=float, default=0.005)
    parser.add_argument("--reconstruction", default="test")
    parser.add_argument("--diffuse", default=os.path.join(base_dir, "test_images", "UVMaps", "Sofa_01_diff_4k.jpg"))
    parser.add_argument("--mask", default=os.path.join(base_dir, "test_images", "UVMaps", "Sofa_01_uv_mask.png"))
    parser.add_argument("--cache", default=os.path.join(base_dir, "outputs", "prediction_cache.sqlite"))
    parser.add_argument("--no-uv-cache", action="store_true", help="Disable reusable island, SLIC and classification-crop caches")
    args = parser.parse_args()

    model_files = {
        "minc": "minc_resnet18/minc_resnet18.pth",
        "minc_legacy": "minc_resnet18/minc_resnet18_old.pth",
        "matsynth": "matsynth_resnet18/matsynth_resnet18.pth",
        "dms": "ml-dms_resnet18/ml-dms_resnet18.pth"
    }

    model_paths = {
        name: os.path.join(base_dir, "models", model_files[name])
        for name in dict.fromkeys(args.models)
    }

    for model_path in model_paths.values():
        if not os.path.isfile(model_path):
            raise FileNotFoundError(model_path)

    diffuse_path = args.diffuse
    mask_path = args.mask

    chunk_name = os.path.splitext(os.path.basename(diffuse_path))[0]
    configuration_name = "_".join(sorted(model_paths)) + "_" + args.method

    output_dir = os.path.join(base_dir, "outputs", "superpixel", args.reconstruction, configuration_name, chunk_name)
    debug_dir = os.path.join(output_dir, "crops")


    raw_material_id_path = os.path.join(output_dir, "material_id_superpixel_raw.png")
    material_id_path = os.path.join(output_dir, "material_id_superpixel_merged.png")
    tie_preview_path = os.path.join(output_dir, "material_id_tie_preview_raw.png")
    superpixel_preview_path = os.path.join(output_dir, "superpixel_boundaries.png")
    merged_preview_path = os.path.join(output_dir, "merged_material_boundaries.png")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Device:", device)

    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    model = MaterialClassifier(model_paths, device, method=args.method, cache_path=args.cache, tie_tolerance=args.tie_tolerance)
    classes = model.classes
    transform = None

    print("Models:", ", ".join(args.models))
    print("Method:", args.method)
    print("Available material classes:", classes)

    missing_colors = sorted(set(classes) - set(MATERIAL_COLORS))

    if missing_colors:
        print("Materials missing ID-map colours:", missing_colors)

    diffuse = Image.open(diffuse_path).convert("RGB")
    mask_image = Image.open(mask_path).convert("L")

    if diffuse.size != mask_image.size:
        raise ValueError("Diffuse and mask dimensions do not match.")

    mask = np.array(mask_image)
    uv_cache = None
    if not args.no_uv_cache:
        uv_cache_path = os.path.join(base_dir, "outputs", "superpixel", args.reconstruction, "_uv_cache", chunk_name + ".sqlite")
        uv_cache = UVPreprocessCache(uv_cache_path, diffuse_path, mask_path)
        print("UV cache:", "new or invalidated" if uv_cache.rebuilt else "reusing", uv_cache_path, flush=True)
    islands = uv_cache.load_islands() if uv_cache is not None else None
    if islands is None:
        islands = get_connected_islands(mask)
        if uv_cache is not None:
            uv_cache.store_islands(islands)

    print()
    print(f"Found {len(islands)} UV islands")

    full_height = diffuse.height
    full_width = diffuse.width

    full_segment_map = np.zeros((full_height, full_width), dtype=np.int32)

    all_regions = []
    all_merged_regions = []

    global_segment_offset = 0
    global_merged_label = 1

    full_merged_label_map = np.zeros((full_height, full_width), dtype=np.int32)

    full_merged_label_map = np.zeros((full_height, full_width), dtype=np.int32)

    for island_index, prepared in enumerate(prepared_islands(islands, diffuse, uv_cache), start=1):
        island = islands[island_index - 1]

        x = island["x"]
        y = island["y"]
        width = island["width"]
        height = island["height"]

        island_image, island_mask, segments, segment_ids, regions = prepared

        parent_classification = classify_region(island_image, island_mask, model, classes, transform, device, uv_cache=uv_cache)

        remapped_segments = np.zeros_like(segments, dtype=np.int32)
        segment_mapping = {}

        for local_index, segment_id in enumerate(segment_ids, start=1):
            global_id = global_segment_offset + local_index
            remapped_segments[segments == segment_id] = global_id
            segment_mapping[int(segment_id)] = global_id

        full_segment_map[y:y + height, x:x + width] = np.where(remapped_segments > 0, remapped_segments, full_segment_map[y:y + height, x:x + width])
        global_segment_offset += len(segment_ids)

        #regions = build_superpixel_regions(island, island_image, segments)

        for region in regions:
            region["global_segment_id"] = segment_mapping[region["segment_id"]]

        classify_superpixel_regions(regions, parent_classification, model, classes, transform, device, uv_cache=uv_cache)
        
        smooth_low_confidence_regions(regions, segments)
        verify_disagreement_clusters_with_sliding_windows(regions, segments, island_image, island_mask, model, classes, transform, device, uv_cache=uv_cache)

        merge_small_material_clusters(regions, segments)
        merged_regions = build_merged_regions(regions, segments, island)

        global_merged_label = add_merged_regions_to_label_map(merged_regions, full_merged_label_map, global_merged_label)

        all_regions.extend(regions)
        all_merged_regions.extend(merged_regions)

        parent_label = (parent_classification["results"][0][0] if parent_classification is not None else "unknown")

        parent_confidence = (parent_classification["results"][0][1] if parent_classification is not None else 0.0)

        print()
        print(
            f"Island {island_index}: "
            f"{len(regions)} superpixels "
            f"-> {len(merged_regions)} merged regions "
            f"| Parent: "
            f"{parent_label} "
            f"{parent_confidence * 100:.2f}%"
        )

    print()
    print("=" * 80)
    print(f"Final superpixel regions: {len(all_regions)}")
    print("=" * 80)

    for index, region in enumerate(all_regions, start=1):
        material = region["resolved_material"]
        confidence = region["resolved_confidence"]

        flags = []

        if region.get("fallback_used", False):
            flags.append("fallback")

        if region.get("rotation_used", False):
            flags.append(f"rotated {region['rotation_angle']:.1f}deg")

        if region.get("neighbor_smoothed", False):
            flags.append("neighbor-smoothed")

        if region.get("sliding_verified", False):
            flags.append(f"sliding-verified {region.get('sliding_window_count', 0)} windows")

        if region.get("sliding_reclassified", False):
            flags.append("sliding-reclassified")

        suffix = (" | " + ", ".join(flags) if flags else "")

        print(
            f"Region {index:03d} "
            f"[{region['x']}, {region['y']}] "
            f"{region['width']}x{region['height']} "
            f"Area {region['area']} "
            f"| {material} "
            f"{confidence * 100:.2f}%"
            f"{suffix}"
        )

        save_debug_crop(region,debug_dir,index)

    generate_material_id_map(diffuse.size, all_regions, raw_material_id_path)
    generate_tie_preview(all_regions, raw_material_id_path, tie_preview_path)
    generate_material_id_map(diffuse.size, all_merged_regions, material_id_path)
    generate_superpixel_preview(diffuse, full_segment_map, mask, superpixel_preview_path)
    generate_superpixel_preview(diffuse, full_merged_label_map, mask, merged_preview_path)

    os.makedirs(output_dir, exist_ok=True)

    np.savez_compressed(os.path.join(output_dir, "topology_segments.npz"), segments=full_segment_map)

    topology_metadata = {
        "chunk_name": chunk_name,
        "regions": [],
        "colors": {name: list(color) for name, color in MATERIAL_COLORS.items()}
    }

    for region in all_regions:
        topology_metadata["regions"].append({
            "id": int(region["global_segment_id"]),
            "material": region["resolved_material"],
            "confidence": float(region["resolved_confidence"]),
            "results": [[name, float(score)] for name, score in region.get("results", [])]
        })

    with open(os.path.join(output_dir, "topology_regions.json"), "w", encoding="utf-8") as file:
        json.dump(topology_metadata, file, indent=2)

    print()
    print(f"Merged material regions: {len(all_merged_regions)}")

    print()
    print("Raw superpixel ID map saved to:")
    print(raw_material_id_path)

    print()
    print("Merged Material ID map saved to:")
    print(material_id_path)

    print()
    print("Superpixel boundary preview saved to:")
    print(superpixel_preview_path)

    print()
    print("Merged material boundary preview saved to:")
    print(merged_preview_path)

    print("Tie preview saved to:", tie_preview_path)
    print(f"Prediction cache: {model.hits} hits, {model.misses} misses")
    if uv_cache is not None:
        uv_cache.print_summary()
        uv_cache.close()
    model.close()


if __name__ == "__main__":
    main()
