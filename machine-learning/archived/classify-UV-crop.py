"""
This is the MINC-2500 UV Texture Material Classification Test

It loads a ResNet18 model that is trained and fine-tuned using the MINC-2500 material dataset and 
applies it to a diffuse UV texture using a corresponding binary UV mask.

Instead of classifying arbitrary rectangular sections of the texture, the UV mask is used 
to identify the actual UV geometry belonging to the model.

The classification pipeline:

1. Find the individual connected UV islands within the texture mask.
2. Ignores UV islands that are too small to provide useful classification.
3. Crops each island to its valid UV geometry.
4. Recursively splits irregular UV regions when doing so produces denser and more useful rectangular classification regions.
    - Optionally: rotates UV regions when rotation produces a larger valid classification crop with less unused space.
5. Classifies each resulting region using the trained MINC ResNet18 model.
6. Subdivides sufficiently large regions into smaller material regions when the child classifications do not reach the required consensus about material composition.
7. Reports the most probable MINC material classes and confidence values for each final region.
8. Generates a colour coded material ID map using the original UV masks.

Purpose:

This script extends the baseline material classification test by making the classification process aware 
of the geometry of the UV texture atlas.

The baseline classifier demonstrated that rectangular image regions can contain multiple UV islands, 
texture dilation, and unused background space. These artifacts can SIGNIFICANTLY affect the material classification results.

Using the UV mask allows classification samples to be extracted from valid texture regions while reducing unrelated pixels 
and empty texture space. Recursive geometry splitting further attempts to create dense classification regions, while 
material subdivision allows larger UV regions containing multiple materials to be divided into smaller independently 
classified areas.

The resulting material classifications are written back into UV texture space as a material ID map for later use by the digital twin pipeline.
"""

import os
import cv2
import torch
import torch.nn as nn
import numpy as np

from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights

#Parameters for Classification:

#Ignore UV islands smaller than this many pixels.
MIN_COMPONENT_AREA = 500

#Minimum dimensions required for a region to be considered classifiable.
MIN_WIDTH = 128
MIN_HEIGHT = 128
#Prevents very long or thin regions from being classified.
MAX_ASPECT_RATIO = 4.0

#Geometry splitting parameters:
#Controls when irregular UV regions should be split into smaller regions.
MIN_FILL_RATIO = 0.75
MIN_SPLIT_IMPROVEMENT = 0.10

#Allow UV regions to be rotated to produce a better crop for classificaiton. (less wasted space around the UV island)
ROTATION_IMPROVEMENT_THRESHOLD = 0.05
ENABLE_ROTATION = True

#Confidence requirements used when evaluating material predictions.
MATERIAL_CONFIDENCE_THRESHOLD = 0.85
MATERIAL_MARGIN_THRESHOLD = 0.30

#Material subdivision parameters.
#Control recursive depth, child agreement, and minimum child crop size.
MAX_MATERIAL_DEPTH = 2
CHILD_CONSENSUS_THRESHOLD = 0.75
MIN_MATERIAL_WIDTH = 128
MIN_MATERIAL_HEIGHT = 128

#Save classifier input crops for visual debugging and result validation.
SAVE_DEBUG_CROPS = True

#Colors for generated ID map
MATERIAL_COLORS = {
    "brick": (180, 60, 40),
    "carpet": (150, 90, 180),
    "ceramic": (240, 180, 80),
    "fabric": (220, 100, 160),
    "foliage": (60, 160, 70),
    "food": (240, 130, 60),
    "glass": (80, 200, 230),
    "hair": (100, 70, 50),
    "leather": (120, 80, 45),
    "metal": (130, 140, 150),
    "mirror": (180, 220, 240),
    "other": (100, 100, 100),
    "painted": (80, 120, 230),
    "paper": (240, 240, 200),
    "plastic": (230, 80, 220),
    "polishedstone": (180, 180, 210),
    "skin": (220, 170, 140),
    "sky": (80, 150, 240),
    "stone": (110, 110, 110),
    "tile": (230, 210, 100),
    "wallpaper": (200, 140, 90),
    "water": (40, 100, 220),
    "wood": (130, 80, 35)
}

#loads the machine learning model and its class labels.
#rebuilds the final fully connected layer to match the number of saved classes.
def load_model(model_path, device):
    checkpoint = torch.load( model_path,map_location=device)

    classes = checkpoint["classes"]

    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    return model, classes

#Prepare a masked image region and classify it with the trained material model.
#Returns the top predictions in descending confidence order.
def classify_crop(image, mask, model, classes, transform, device, top_k=5):

    classification_image = prepare_classification_image(image, mask)
    tensor = transform(classification_image.convert("RGB")).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(tensor)

        probabilities = torch.softmax(output, dim=1)[0]

    values, indices = torch.topk(probabilities, min(top_k, len(classes)))

    return [(classes[index.item()], probability.item()) for probability, index in zip(values, indices)]

#Finds separate connected regions in the Uv mask. Small isolated components are ignored using MIN_COMPONENT_AREA. 
#Too small to realistically classify. 
# TODO: Thought: might want to group similar ones together?
def get_connected_islands(mask):
    #mask
    binary = (mask > 127).astype(np.uint8)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    #set up the islands
    islands = []

    for label_index in range(1, count):
        x = stats[label_index, cv2.CC_STAT_LEFT]
        y = stats[label_index, cv2.CC_STAT_TOP]

        width = stats[label_index, cv2.CC_STAT_WIDTH]
        height = stats[label_index, cv2.CC_STAT_HEIGHT]

        area = stats[label_index, cv2.CC_STAT_AREA]

        if area < MIN_COMPONENT_AREA:
            continue
        #mask
        island_mask = (labels[y:y + height, x:x + width] == label_index).astype(np.uint8)

        islands.append(
            {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "mask": island_mask
            }
        )

    return islands

#returns the smallest AABB (axis-aligned bounding box) containing all active mask pixels.
def tight_bounds(mask):
    ys, xs = np.where(mask > 0)

    if len(xs) == 0:
        return None

    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)

#Measure how much of a rectangular crop is occupied by the valid mask pixels.
def fill_ratio(mask):
    if mask.size == 0:
        return 0.0

    return (np.count_nonzero(mask) / mask.size)

#Return the larger w/h ratio so portrait and landscape regions are treated the same.
def aspect_ratio(width, height):
    if width <= 0 or height <= 0:
        return float("inf")

    return max(width / height, height / width)

#Check whether a region is ACTUALLY large enough and not excessively thin for classification. Needs some meat.
def region_is_classifiable(width, height):
    return (width >= MIN_WIDTH and height >= MIN_HEIGHT and aspect_ratio(width, height) <= MAX_ASPECT_RATIO)

#Remove the empty mask space around a region and return its cropped dimensions and its fill ratio.
def trimmed_region(mask):
    bounds = tight_bounds(mask)

    if bounds is None:
        return None

    x1, y1, x2, y2 = bounds

    trimmed = mask[y1:y2, x1:x2]

    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "mask": trimmed,
        "width": x2 - x1,
        "height": y2 - y1,
        "fill": fill_ratio(trimmed)
    }

#Evaluates one possible horizontal or vertical split of a mask.
#A split scores well, when both resulting regions contain dense, usable mask coverage.
def evaluate_geometry_split(mask, direction, position):
    height, width = mask.shape

    if direction == "vertical":
        mask_a = mask[:, :position]
        mask_b = mask[:, position:]
    else: #horizontal
        mask_a = mask[:position,:]
        mask_b = mask[position:,:]

    region_a = trimmed_region(mask_a)
    region_b = trimmed_region(mask_b)

    if region_a is None or region_b is None:
        return None

    if not region_is_classifiable(region_a["width"], region_a["height"]):
        return None

    if not region_is_classifiable(region_b["width"], region_b["height"]):
        return None

    pixels_a = np.count_nonzero(region_a["mask"])
    pixels_b = np.count_nonzero(region_b["mask"])
    total_pixels = (pixels_a + pixels_b)

    if total_pixels == 0:
        return None
    #weighted fill:
    weighted_fill = (region_a["fill"] * pixels_a + region_b["fill"] * pixels_b) / total_pixels

    return {
        "direction": direction,
        "position": position,
        "score": weighted_fill
    }

#Search possible horizontal and vertical split positions and keep the highest scoring option.
def find_best_geometry_split(mask):
    height, width = mask.shape

    candidates = []

    step = max(8, min(width, height) // 64)

    for x in range( MIN_WIDTH,width - MIN_WIDTH + 1,step):
        candidate = evaluate_geometry_split(mask, "vertical", x)

        if candidate is not None:
            candidates.append(candidate)

    for y in range( MIN_HEIGHT,height - MIN_HEIGHT + 1,step):
        candidate = evaluate_geometry_split(mask, "horizontal", y)

        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate["score"])

#Recursively divide any irregular UV geometry into even denser rectangular regions.
#splitting stops when the region is filled enough, too small, or no useful split exists.
def geometry_crop(image, mask, origin_x, origin_y, depth=0):
    bounds = tight_bounds(mask)

    if bounds is None:
        return []

    x1, y1, x2, y2 = bounds

    image = image.crop((x1, y1, x2, y2))

    mask = mask[y1:y2, x1:x2]

    origin_x += x1
    origin_y += y1

    height, width = mask.shape

    current_fill = fill_ratio(mask)

    if not region_is_classifiable(width, height):
        return [
            {
                "image": image,
                "mask": mask,
                "x": origin_x,
                "y": origin_y,
                "width": width,
                "height": height,
                "fill_ratio": current_fill,
                "geometry_depth": depth
            }
        ]

    if current_fill >= MIN_FILL_RATIO:
        return [
            {
                "image": image,
                "mask": mask,
                "x": origin_x,
                "y": origin_y,
                "width": width,
                "height": height,
                "fill_ratio": current_fill,
                "geometry_depth": depth
            }
        ]

    split = find_best_geometry_split(mask)

    if split is None:
        return [
            {
                "image": image,
                "mask": mask,
                "x": origin_x,
                "y": origin_y,
                "width": width,
                "height": height,
                "fill_ratio": current_fill,
                "geometry_depth": depth
            }
        ]

    improvement = (split["score"] - current_fill)

    if improvement < MIN_SPLIT_IMPROVEMENT:
        return [
            {
                "image": image,
                "mask": mask,
                "x": origin_x,
                "y": origin_y,
                "width": width,
                "height": height,
                "fill_ratio": current_fill,
                "geometry_depth": depth
            }
        ]

    position = split["position"]

    regions = []

    if split["direction"] == "vertical":
        left_image = image.crop((0, 0, position, height))
        right_image = image.crop((position, 0, width, height))

        left_mask = mask[:,:position]
        right_mask = mask[:,position:]

        regions.extend(geometry_crop(left_image, left_mask, origin_x, origin_y, depth + 1))
        regions.extend(geometry_crop(right_image, right_mask, origin_x + position, origin_y, depth + 1))

    else:
        top_image = image.crop((0, 0, width, position))
        bottom_image = image.crop((0, position, width, height))

        top_mask = mask[:position, :]
        bottom_mask = mask[position:, :]

        regions.extend(geometry_crop(top_image, top_mask, origin_x, origin_y, depth + 1))
        regions.extend(geometry_crop(bottom_image, bottom_mask, origin_x, origin_y + position, depth + 1))

    return regions

#Splits a masked material region into four quadrants and trims each quadrant to its valid UV geometry while preserving the texture coordinates.
def split_into_quadrants(image, mask, origin_x, origin_y):
    image_width, image_height = image.size
    mask_height, mask_width = mask.shape

    if image_width != mask_width or image_height != mask_height:
        raise ValueError(f"split_into_quadrants mismatch: image={image_width}x{image_height}, mask={mask_width}x{mask_height}")

    width = image_width
    height = image_height

    mid_x = width // 2
    mid_y = height // 2

    definitions = [
        (
            0,
            0,
            mid_x,
            mid_y
        ),
        (
            mid_x,
            0,
            width,
            mid_y
        ),
        (
            0,
            mid_y,
            mid_x,
            height
        ),
        (
            mid_x,
            mid_y,
            width,
            height
        )
    ]

    children = []

    for x1, y1, x2, y2 in definitions:
        child_mask = mask[y1:y2, x1:x2]

        if image.size != (mask.shape[1], mask.shape[0]):
            raise ValueError(f"geometry_crop mismatch: image={image.size}, mask={(mask.shape[1], mask.shape[0])}")


        bounds = tight_bounds(child_mask)

        if bounds is None:
            continue

        bx1, by1, bx2, by2 = bounds

        child_image = image.crop((x1 + bx1, y1 + by1, x1 + bx2, y1 + by2))
        child_mask = child_mask[by1:by2, bx1:bx2]

        child_x = (origin_x + x1 + bx1)
        child_y = (origin_y + y1 + by1)

        children.append(
            {
                "image": child_image,
                "mask": child_mask,
                "x": child_x,
                "y": child_y,
                "width": bx2 - bx1,
                "height": by2 - by1
            }
        )

    return children

#Determines whether a material prediction is sufficiently confident based on both the top prediction probability and its margin difference over second place.
def prediction_is_confident(results):
    if len(results) < 2:
        return True

    top_probability = results[0][1]
    second_probability = results[1][1]

    #get margin
    margin = (top_probability - second_probability)

    return top_probability >= MATERIAL_CONFIDENCE_THRESHOLD and margin >= MATERIAL_MARGIN_THRESHOLD
    

# Recursively subdivides a material region when its child classifications do not reach an agreement on a single material.
# Subdivision will stop when the maximum depth or minimum region size is reached.
def material_subdivide(region, model, classes, transform, device, depth=0):
    results = classify_crop(region["image"], region["mask"], model, classes, transform, device)

    region["results"] = results
    region["material_depth"] = depth
    region["resolved_material"] = results[0][0]
    region["resolved_confidence"] = results[0][1]

    width = region["width"]
    height = region["height"]

    if depth >= MAX_MATERIAL_DEPTH:
        return [region]

    if (width < MIN_MATERIAL_WIDTH * 2 or height < MIN_MATERIAL_HEIGHT * 2):
        return [region]

    children = split_into_quadrants(region["image"], region["mask"], region["x"], region["y"])

    classifiable_children = [
        child for child in children if (child["width"] >= MIN_MATERIAL_WIDTH
            and child["height"] >= MIN_MATERIAL_HEIGHT
            and aspect_ratio(child["width"], child["height"]) <= MAX_ASPECT_RATIO
        )
    ]

    if len(classifiable_children) < 2:
        return [region]

    for child in classifiable_children:
        child["results"] = classify_crop(child["image"], child["mask"], model, classes, transform, device)

    (consensus_material, consensus_ratio, consensus_confidence) = get_child_consensus(classifiable_children)

    if (consensus_ratio >= CHILD_CONSENSUS_THRESHOLD):
        region["resolved_material"] = (consensus_material)
        region["resolved_confidence"] = (consensus_confidence)
        region["child_consensus"] = (consensus_ratio)

        return [region]

    final_regions = []

    for child in classifiable_children:
        final_regions.extend(material_subdivide( child, model, classes, transform, device, depth + 1))

    return final_regions

# Saves the final image crop used by the classifier for debugging and visual validation of the classification pipeline.
def save_debug_crop(region, output_dir, index):
    os.makedirs(output_dir, exist_ok=True)

    material = region["results"][0][0]
    confidence = int(region["results"][0][1] * 100)

    filename = f"crop_{index:03d}_{material}_{confidence}.png"

    path = os.path.join(output_dir, filename)
    classification_image = prepare_classification_image(region["image"], region["mask"])
    classification_image.save(path)

# Determines the dominant material prediction among the set of child regions and returns its agreement ratio and classification confidence average. 
def get_child_consensus(children):
    predictions = [child["results"][0][0] for child in children]

    counts = {}

    for material in predictions:
        counts[material] = (counts.get(material, 0) + 1)

    consensus_material = max(counts, key=counts.get)
    consensus_count = counts[consensus_material]
    consensus_ratio = (consensus_count / len(predictions))
    matching_confidences = [child["results"][0][1] for child in children if child["results"][0][0] == consensus_material]

    average_confidence = (sum(matching_confidences) / len(matching_confidences))
    return (consensus_material, consensus_ratio, average_confidence)

#Finds the largest rectangular area contained entirely within the valid mask. This reduces unused or invalid texture pixels in the classifier input.
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

            while (stack and stack[-1][1] > current_height):
                index, bar_height = stack.pop()
                area = bar_height * (x - index)

                if area > best_area:
                    best_area = area
                    best_bounds = (index, y - bar_height + 1, x, y + 1)

                start = index

            if (not stack or stack[-1][1] < current_height):
                stack.append((start, current_height))

    return best_bounds

#Rotates an image and its corresponding UV mask by the same angle, expands the output bounds, and then trims unused space around the result.
def rotate_image_and_mask(image, mask, angle):
    rgb = np.array(image.convert("RGB"))

    binary = (mask > 0).astype(np.uint8)
    height, width = binary.shape
    center = (width / 2.0, height / 2.0)

    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cosine = abs(matrix[0, 0])
    sine = abs(matrix[0, 1])

    new_width = int(height * sine + width * cosine)
    new_height = int(height * cosine + width * sine)

    matrix[0, 2] += (new_width / 2.0 - center[0])
    matrix[1, 2] += (new_height / 2.0 - center[1])

    rotated_image = cv2.warpAffine(rgb, matrix, (new_width, new_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    rotated_mask = cv2.warpAffine(binary, matrix, (new_width, new_height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

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

    angle = rectangle[2]
    rect_width, rect_height = rectangle[1]

    if rect_width < rect_height:
        angle += 90.0

    return angle

#Extracts the largest fully valid rectangular texture region from a mask. Fall back to the tight mask bounds when no valid rectangle can be found.
def crop_to_largest_valid_rectangle(image, mask):
    bounds = largest_valid_rectangle(mask)

    if bounds is None:
        bounds = tight_bounds(mask)

    if bounds is None:
        return image, 0

    x1, y1, x2, y2 = bounds
    cropped_image = image.crop((x1, y1, x2, y2))
    area = ((x2 - x1) * (y2 - y1))

    return cropped_image, area

#Prepares a masked UV region for material classification by selecting the largest valid crop. 
#Optionally: rotating the region when doing so produces a sufficiently larger usable classification area.
def prepare_classification_image(image, mask):
    image_width, image_height = image.size
    mask_height, mask_width = mask.shape

    if image_width != mask_width or image_height != mask_height:
        raise ValueError(f"Image/mask size mismatch: image={image_width}x{image_height}, mask={mask_width}x{mask_height}")

    base_image, base_area = (crop_to_largest_valid_rectangle(image,mask))

    if not ENABLE_ROTATION:
        return base_image

    angle = get_best_rotation_angle(mask)

    if abs(angle) < 0.5:
        return base_image

    rotated_image, rotated_mask = (rotate_image_and_mask(image, mask, angle))
    rotated_crop, rotated_area = (crop_to_largest_valid_rectangle(rotated_image, rotated_mask))
    required_area = (base_area * (1.0 + ROTATION_IMPROVEMENT_THRESHOLD))

    if rotated_area >= required_area:
        return rotated_crop

    return base_image

#Generates a colour-coded material ID map by writing each region's resolved material classification back into its original UV coordinates.
def generate_material_id_map(image_size, regions, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    width, height = image_size
    output = np.zeros((height, width, 4), dtype=np.uint8)

    for region in regions:
        material = region.get("resolved_material", region["results"][0][0])

        color = MATERIAL_COLORS.get(material, (255, 255, 255))

        x = region["x"]
        y = region["y"]

        region_width = region["width"]
        region_height = region["height"]

        mask = region["mask"] > 0

        destination = output[y:y + region_height, x:x + region_width]

        destination[mask,0] = color[0]
        destination[mask, 1] = color[1]
        destination[mask, 2] = color[2]
        destination[mask,3] = 255

    Image.fromarray(output, mode="RGBA").save(output_path)

#Runs the complete UV-aware material classification pipeline: 
# Loads the model and textures. 
# Extracts UV islands. 
# Subdivides and classifies material regions.
# Saves debug crops. 
# Generates the final material ID map.
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    model_path = os.path.join(base_dir, "models", "minc_resnet18.pth")
    diffuse_path = os.path.join(base_dir, "test_images", "UVMaps", "Sofa_01_diff_4k.jpg")
    mask_path = os.path.join(base_dir, "test_images", "UVMaps", "Sofa_01_uv_mask.png")
    debug_dir = os.path.join(base_dir, "outputs", "uv_crops")
    material_id_path = os.path.join(base_dir, "outputs", "material_id.png")

    #Use GPU if available.
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Device:", device)

    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    #load the model
    model, classes = load_model(model_path, device)

    weights = ResNet18_Weights.DEFAULT
    transform = weights.transforms()

    #load diffuse as RGB image
    diffuse = Image.open(diffuse_path).convert("RGB")
    #load UV mask as single channel
    mask_image = Image.open(mask_path).convert("L")
    mask = np.array(mask_image)

    if diffuse.size != mask_image.size:
        raise ValueError("Diffuse and mask dimensions do not match.")

    islands = get_connected_islands(mask)

    print()
    print(f"Found {len(islands)} UV islands")

    final_regions = []

    for island_index, island in enumerate(islands, start=1):
        x = island["x"]
        y = island["y"]
        width = island["width"]
        height = island["height"]

        island_image = diffuse.crop((x, y, x + width, y + height))
        geometry_regions = geometry_crop(island_image, island["mask"], x, y)

        print()
        print(f"Island {island_index}: {len(geometry_regions)} geometry regions")

        for region in geometry_regions:
            material_regions = material_subdivide( region,model,classes,transform,device)

            final_regions.extend(material_regions)

    print()
    print("=" * 80)
    print(f"Final material regions: {len(final_regions)}")
    print("=" * 80)

    for index, region in enumerate(final_regions, start=1):
        results = region["results"]

        print()
        print(f"Region {index} [{region['x']}, {region['y']}] {region['width']}x{region['height']} Depth: {region['material_depth']}")

        for rank, (material, probability) in enumerate( results,start=1):
            print(f"  {rank}. {material:<18} {probability * 100:6.2f}%")

        if SAVE_DEBUG_CROPS:
            save_debug_crop( region,debug_dir,index)


    generate_material_id_map( diffuse.size,final_regions,material_id_path)

    print()
    print("Material ID map saved to:")
    print(material_id_path)


if __name__ == "__main__":
    main()