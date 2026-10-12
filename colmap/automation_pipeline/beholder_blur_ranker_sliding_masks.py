import argparse
import csv
import shutil
from pathlib import Path

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
"""
 This BEHOLDER blur-analysis script is designed for photogrammetry rather than photographic aesthetics.
 It uses overlapping sliding windows to find locally sharp regions. Those  regions are converted 
 into a COLMAP-compatible binary mask:
 
 WHITE (255) = COLMAP may extract features here
 BLACK (0)   = COLMAP must ignore this region
 
 Source photographs are NEVER cropped, painted over, altered, or deleted.
 
 Automatic CSV labels:
 
 KEEP: at least --min-keep-coverage of the image remains unmasked
 REVIEW: some useful area remains, but less than the automatic KEEP cutoff
 SKIP: the generated mask is completely black

 Because the reconstruction automation already selects rows marked KEEP, SKIP  frames can be omitted 
 from COLMAP entirely instead of wasting valuable time importing an image that has no usable feature region.
"""

def load_grayscale(path: Path, max_dimension: int = 800):
    """Load an image for analysis while remembering its original dimensions."""
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    if image is None:
        raise ValueError("OpenCV could not read the image.")

    original_height, original_width = image.shape[:2]
    height, width = image.shape[:2]
    largest = max(height, width)

    if largest > max_dimension:
        scale = max_dimension / largest
        image = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    return image, original_width, original_height


def laplacian_score(image: np.ndarray) -> float:
    """Variance of Laplacian: higher values generally indicate sharper detail."""
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def analyze_region(
    region: np.ndarray,
    sharpness_threshold: float,
    min_contrast: float,
    max_saturated_fraction: float,
    max_dark_fraction: float,
):
    """
    Analyze one local image region.

    Regions dominated by saturation, darkness, or near-zero contrast are treated as unusable 
    instead of allowing them to distort the blur measurement.
    """
    score = laplacian_score(region)
    contrast = float(region.std())
    saturated_fraction = float(np.mean(region >= 250))
    dark_fraction = float(np.mean(region <= 5))

    ignored_reason = ""

    if saturated_fraction >= max_saturated_fraction:
        ignored_reason = "SATURATED"
    elif dark_fraction >= max_dark_fraction:
        ignored_reason = "DARK"
    elif contrast < min_contrast:
        ignored_reason = "LOW_TEXTURE"

    usable = ignored_reason == ""
    sharp = usable and score >= sharpness_threshold

    return {
        "score": score,
        "contrast": contrast,
        "saturated_fraction": saturated_fraction,
        "dark_fraction": dark_fraction,
        "usable": usable,
        "sharp": sharp,
        "ignored_reason": ignored_reason,
    }


# -----------------------------------------------------------------------------
# Fixed-grid diagnostics
# -----------------------------------------------------------------------------
# The older tiled approach is retained only as a diagnostic. It is useful when
# inspecting CSV results, but the final mask is generated from overlapping
# sliding windows so that useful regions are not dependent on arbitrary tile
# boundaries.


def tiled_diagnostics(
    image: np.ndarray,
    rows: int,
    cols: int,
    sharpness_threshold: float,
    min_contrast: float,
    max_saturated_fraction: float,
    max_dark_fraction: float,
):
    height, width = image.shape[:2]
    results = []

    for row in range(rows):
        y0 = row * height // rows
        y1 = (row + 1) * height // rows

        for col in range(cols):
            x0 = col * width // cols
            x1 = (col + 1) * width // cols

            tile = image[y0:y1, x0:x1]

            if tile.size == 0:
                continue

            result = analyze_region(
                tile,
                sharpness_threshold,
                min_contrast,
                max_saturated_fraction,
                max_dark_fraction,
            )
            results.append(result)

    usable_scores = [result["score"] for result in results if result["usable"]]
    sharp_tiles = sum(1 for result in results if result["sharp"])

    if usable_scores:
        values = np.asarray(usable_scores, dtype=np.float64)
        mean_score = float(np.mean(values))
        median_score = float(np.median(values))
        p75_score = float(np.percentile(values, 75))
        sharp_tile_fraction = sharp_tiles / len(usable_scores)
    else:
        mean_score = 0.0
        median_score = 0.0
        p75_score = 0.0
        sharp_tile_fraction = 0.0

    return {
        "tile_mean_score": mean_score,
        "tile_median_score": median_score,
        "tile_p75_score": p75_score,
        "sharp_tile_fraction": sharp_tile_fraction,
        "usable_tiles": len(usable_scores),
        "total_tiles": len(results),
    }


# -----------------------------------------------------------------------------
# Sliding-window mask generation
# -----------------------------------------------------------------------------


def sliding_positions(length: int, window_size: int, stride: int):
    """Return window start positions while always covering the far edge."""
    if length <= window_size:
        return [0]

    positions = list(range(0, length - window_size + 1, stride))
    final_position = length - window_size

    if positions[-1] != final_position:
        positions.append(final_position)

    return positions


def generate_sliding_mask(
    image: np.ndarray,
    window_size: int,
    stride: int,
    sharpness_threshold: float,
    min_contrast: float,
    max_saturated_fraction: float,
    max_dark_fraction: float,
    mask_vote_threshold: float,
    close_kernel: int,
):
    """
    Slide overlapping windows across the analysis image and build a binary mask.

    Every usable window votes on the pixels it covers. A sharp window contributes
    a sharp vote. A pixel is kept when enough of its usable overlapping windows
    are sharp according to --mask-vote-threshold.

    This voting approach is more selective than simply turning an entire region
    white whenever ANY overlapping window happens to be sharp.
    """
    height, width = image.shape[:2]

    actual_window_width = min(window_size, width)
    actual_window_height = min(window_size, height)

    x_positions = sliding_positions(width, actual_window_width, stride)
    y_positions = sliding_positions(height, actual_window_height, stride)

    usable_votes = np.zeros((height, width), dtype=np.uint16)
    sharp_votes = np.zeros((height, width), dtype=np.uint16)

    total_windows = 0
    usable_windows = 0
    sharp_windows = 0
    scores = []

    for y0 in y_positions:
        y1 = min(height, y0 + actual_window_height)

        for x0 in x_positions:
            x1 = min(width, x0 + actual_window_width)
            window = image[y0:y1, x0:x1]

            if window.size == 0:
                continue

            total_windows += 1

            result = analyze_region(
                window,
                sharpness_threshold,
                min_contrast,
                max_saturated_fraction,
                max_dark_fraction,
            )

            scores.append(result["score"])

            if result["usable"]:
                usable_windows += 1
                usable_votes[y0:y1, x0:x1] += 1

            if result["sharp"]:
                sharp_windows += 1
                sharp_votes[y0:y1, x0:x1] += 1

    vote_ratio = np.zeros((height, width), dtype=np.float32)
    has_usable_vote = usable_votes > 0

    vote_ratio[has_usable_vote] = (
        sharp_votes[has_usable_vote].astype(np.float32)
        / usable_votes[has_usable_vote].astype(np.float32)
    )

    analysis_mask = np.where(
        has_usable_vote
        & (sharp_votes > 0)
        & (vote_ratio >= mask_vote_threshold),
        255,
        0,
    ).astype(np.uint8)

    # Close small black holes and tiny gaps between nearby good regions without
    # inventing large new areas of image data.
    if close_kernel > 1:
        if close_kernel % 2 == 0:
            close_kernel += 1

        kernel = np.ones((close_kernel, close_kernel), dtype=np.uint8)
        analysis_mask = cv2.morphologyEx(
            analysis_mask,
            cv2.MORPH_CLOSE,
            kernel,
        )

    coverage_fraction = (
        float(np.count_nonzero(analysis_mask)) / analysis_mask.size
        if analysis_mask.size
        else 0.0
    )

    usable_pixel_fraction = (
        float(np.count_nonzero(has_usable_vote)) / has_usable_vote.size
        if has_usable_vote.size
        else 0.0
    )

    if scores:
        values = np.asarray(scores, dtype=np.float64)
        mean_score = float(np.mean(values))
        median_score = float(np.median(values))
        p75_score = float(np.percentile(values, 75))
    else:
        mean_score = 0.0
        median_score = 0.0
        p75_score = 0.0

    return {
        "mask": analysis_mask,
        "mask_coverage_fraction": coverage_fraction,
        "usable_pixel_fraction": usable_pixel_fraction,
        "sliding_mean_score": mean_score,
        "sliding_median_score": median_score,
        "sliding_p75_score": p75_score,
        "usable_windows": usable_windows,
        "sharp_windows": sharp_windows,
        "total_windows": total_windows,
        "sharp_window_fraction": (
            sharp_windows / usable_windows if usable_windows else 0.0
        ),
    }


def save_full_resolution_mask(
    analysis_mask: np.ndarray,
    original_width: int,
    original_height: int,
    mask_path: Path,
):
    """
    Resize the binary analysis mask back to the ORIGINAL image dimensions.

    Nearest-neighbour interpolation keeps the mask binary (0 or 255), which is
    appropriate for COLMAP feature masks.
    """
    full_mask = cv2.resize(
        analysis_mask,
        (original_width, original_height),
        interpolation=cv2.INTER_NEAREST,
    )

    full_mask = np.where(full_mask > 0, 255, 0).astype(np.uint8)

    mask_path.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(mask_path), full_mask):
        raise IOError(f"OpenCV could not write mask: {mask_path}")


# -----------------------------------------------------------------------------
# Files / paths
# -----------------------------------------------------------------------------


def find_images(root: Path):
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def resolve_image_root(root: Path):
    """
    If the supplied project contains an 'images' directory, use that directory
    automatically. Otherwise treat the supplied folder itself as image_path.

    This makes both of these convenient:
        ...\rail car 4
        ...\\rail car 4\\images
    """
    images_child = root / "images"

    if images_child.is_dir() and find_images(images_child):
        return images_child

    return root


def default_mask_root(requested_root: Path, image_root: Path):
    # Standard BEHOLDER project layout: project/images -> project/masks
    if image_root.name.lower() == "images":
        return image_root.parent / "masks"

    # Flat image folder: create a sibling instead of putting masks inside the
    # source directory (which would confuse recursive image discovery).
    return requested_root.with_name(requested_root.name + "_masks")


def project_name(root: Path, image_path: Path) -> str:
    relative = image_path.relative_to(root)

    if len(relative.parts) > 1:
        return relative.parts[0]

    return root.name


def colmap_mask_relative_path(image_root: Path, image_path: Path) -> Path:
    """
    COLMAP requires:
        image: abc/012.jpg
        mask:  abc/012.jpg.png

    Note that '.png' is APPENDED; it does not replace '.jpg'.
    """
    relative = image_path.relative_to(image_root)
    return Path(str(relative) + ".png")


# -----------------------------------------------------------------------------
# CSV labelling
# -----------------------------------------------------------------------------


def assign_flag(mask_coverage_fraction: float, min_keep_coverage: float):
    if mask_coverage_fraction <= 0.0:
        return "SKIP", "EMPTY"

    if mask_coverage_fraction >= min_keep_coverage:
        if mask_coverage_fraction >= 0.95:
            return "KEEP", "FULL"
        return "KEEP", "PARTIAL"

    return "REVIEW", "LOW_COVERAGE"


def apply_percentiles(rows):
    by_project = {}

    for row in rows:
        by_project.setdefault(row["project"], []).append(row)

    for project_rows in by_project.values():
        project_rows.sort(key=lambda row: row["mask_coverage_fraction"])
        count = len(project_rows)

        for index, row in enumerate(project_rows):
            row["percentile_within_project"] = (
                100.0 if count == 1 else 100.0 * index / (count - 1)
            )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate BEHOLDER blur scores plus COLMAP feature masks using "
            "overlapping sliding-window Laplacian analysis."
        )
    )

    parser.add_argument(
        "root",
        help=(
            "BEHOLDER project folder or images folder. If <root>\\images exists, "
            "that directory is used automatically."
        ),
    )

    parser.add_argument(
        "--output",
        default="blur_scores_sliding_masks.csv",
        help="CSV output path. Default: blur_scores_sliding_masks.csv",
    )

    parser.add_argument(
        "--mask-root",
        help=(
            "Root folder for generated COLMAP masks. Default: project\\masks "
            "when an images folder is detected, otherwise <root>_masks."
        ),
    )

    # Fixed-grid diagnostics retained from the tiled version.
    parser.add_argument("--rows", type=int, default=4, help="Diagnostic tile rows. Default: 4")
    parser.add_argument("--cols", type=int, default=6, help="Diagnostic tile columns. Default: 6")

    # Sliding-window settings.
    parser.add_argument(
        "--window-size",
        type=int,
        default=192,
        help="Sliding-window size after analysis resize. Default: 192",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=64,
        help="Sliding-window stride after analysis resize. Default: 64",
    )

    parser.add_argument(
        "--sharpness-threshold",
        type=float,
        default=30.0,
        help="Local Laplacian score required for a window to count as sharp. Default: 30",
    )

    parser.add_argument(
        "--mask-vote-threshold",
        type=float,
        default=0.25,
        help=(
            "Fraction of overlapping usable windows that must be sharp for a "
            "pixel to remain white. Default: 0.25"
        ),
    )

    parser.add_argument(
        "--min-keep-coverage",
        type=float,
        default=0.25,
        help=(
            "Automatically KEEP an image when at least this fraction of the "
            "final mask is white. Default: 0.25"
        ),
    )

    parser.add_argument(
        "--min-contrast",
        type=float,
        default=5.0,
        help="Windows below this grayscale standard deviation are low-texture. Default: 5",
    )

    parser.add_argument(
        "--max-saturated-fraction",
        type=float,
        default=0.20,
        help="Ignore windows with at least this fraction nearly white. Default: 0.20",
    )

    parser.add_argument(
        "--max-dark-fraction",
        type=float,
        default=0.80,
        help="Ignore windows with at least this fraction nearly black. Default: 0.80",
    )

    parser.add_argument(
        "--close-kernel",
        type=int,
        default=5,
        help="Morphological closing kernel for tiny mask holes/gaps. 0 disables. Default: 5",
    )

    parser.add_argument(
        "--max-dimension",
        type=int,
        default=800,
        help="Resize longest side for analysis only. Masks are saved at original size. Default: 800",
    )

    parser.add_argument(
        "--copy-review",
        action="store_true",
        help="Copy REVIEW images to a separate folder. Originals remain untouched.",
    )

    parser.add_argument(
        "--review-folder",
        default="blur_review_sliding_masks",
        help="Folder used with --copy-review.",
    )

    args = parser.parse_args()

    if args.rows < 1 or args.cols < 1:
        raise SystemExit("--rows and --cols must be at least 1.")

    if args.window_size < 16:
        raise SystemExit("--window-size must be at least 16.")

    if args.stride < 1:
        raise SystemExit("--stride must be at least 1.")

    if not 0.0 <= args.mask_vote_threshold <= 1.0:
        raise SystemExit("--mask-vote-threshold must be between 0 and 1.")

    if not 0.0 <= args.min_keep_coverage <= 1.0:
        raise SystemExit("--min-keep-coverage must be between 0 and 1.")

    requested_root = Path(args.root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not requested_root.exists():
        raise SystemExit(f"Folder does not exist: {requested_root}")

    image_root = resolve_image_root(requested_root)
    mask_root = (
        Path(args.mask_root).expanduser().resolve()
        if args.mask_root
        else default_mask_root(requested_root, image_root)
    )

    images = find_images(image_root)

    if not images:
        raise SystemExit(f"No supported images found under: {image_root}")

    print(f"Image root: {image_root}")
    print(f"Found {len(images):,} images.")
    print(f"Mask root: {mask_root}")
    print(
        f"Sliding windows: {args.window_size}px, stride {args.stride}px, "
        f"sharpness >= {args.sharpness_threshold:g}"
    )
    print(
        f"KEEP: >= {args.min_keep_coverage * 100:.0f}% final white-mask coverage; "
        "all-black masks are SKIP."
    )
    print("Original photographs will not be modified.")
    print()

    rows = []

    for index, path in enumerate(images, start=1):
        try:
            image, original_width, original_height = load_grayscale(
                path,
                args.max_dimension,
            )

            global_score = laplacian_score(image)

            tiled = tiled_diagnostics(
                image,
                args.rows,
                args.cols,
                args.sharpness_threshold,
                args.min_contrast,
                args.max_saturated_fraction,
                args.max_dark_fraction,
            )

            sliding = generate_sliding_mask(
                image,
                args.window_size,
                args.stride,
                args.sharpness_threshold,
                args.min_contrast,
                args.max_saturated_fraction,
                args.max_dark_fraction,
                args.mask_vote_threshold,
                args.close_kernel,
            )

            mask_relative = colmap_mask_relative_path(image_root, path)
            mask_path = mask_root / mask_relative

            save_full_resolution_mask(
                sliding["mask"],
                original_width,
                original_height,
                mask_path,
            )

            flag, mask_status = assign_flag(
                sliding["mask_coverage_fraction"],
                args.min_keep_coverage,
            )

            rows.append(
                {
                    "project": project_name(image_root, path),
                    "relative_path": str(path.relative_to(image_root)),
                    "mask_relative_path": str(mask_relative),
                    "mask_status": mask_status,
                    "sharpness_score": global_score,
                    "tile_mean_score": tiled["tile_mean_score"],
                    "tile_median_score": tiled["tile_median_score"],
                    "tile_p75_score": tiled["tile_p75_score"],
                    "sharp_tile_fraction": tiled["sharp_tile_fraction"],
                    "usable_tiles": tiled["usable_tiles"],
                    "total_tiles": tiled["total_tiles"],
                    "sliding_mean_score": sliding["sliding_mean_score"],
                    "sliding_median_score": sliding["sliding_median_score"],
                    "sliding_p75_score": sliding["sliding_p75_score"],
                    "sharp_window_fraction": sliding["sharp_window_fraction"],
                    "usable_pixel_fraction": sliding["usable_pixel_fraction"],
                    "mask_coverage_fraction": sliding["mask_coverage_fraction"],
                    "usable_windows": sliding["usable_windows"],
                    "sharp_windows": sliding["sharp_windows"],
                    "total_windows": sliding["total_windows"],
                    "percentile_within_project": 0.0,
                    "flag": flag,
                }
            )

        except Exception as exc:
            rows.append(
                {
                    "project": project_name(image_root, path),
                    "relative_path": str(path.relative_to(image_root)),
                    "mask_relative_path": "",
                    "mask_status": "ERROR",
                    "sharpness_score": -1.0,
                    "tile_mean_score": -1.0,
                    "tile_median_score": -1.0,
                    "tile_p75_score": -1.0,
                    "sharp_tile_fraction": 0.0,
                    "usable_tiles": 0,
                    "total_tiles": args.rows * args.cols,
                    "sliding_mean_score": -1.0,
                    "sliding_median_score": -1.0,
                    "sliding_p75_score": -1.0,
                    "sharp_window_fraction": 0.0,
                    "usable_pixel_fraction": 0.0,
                    "mask_coverage_fraction": 0.0,
                    "usable_windows": 0,
                    "sharp_windows": 0,
                    "total_windows": 0,
                    "percentile_within_project": 0.0,
                    "flag": f"ERROR: {exc}",
                }
            )

        if index % 250 == 0 or index == len(images):
            print(f"  {index:,}/{len(images):,}")

    valid_rows = [row for row in rows if row["sharpness_score"] >= 0]
    apply_percentiles(valid_rows)

    rows.sort(
        key=lambda row: (
            row["project"].lower(),
            row["mask_coverage_fraction"],
            row["sliding_median_score"],
        )
    )

    fieldnames = [
        "project",
        "relative_path",
        "mask_relative_path",
        "mask_status",
        "sharpness_score",
        "tile_mean_score",
        "tile_median_score",
        "tile_p75_score",
        "sharp_tile_fraction",
        "usable_tiles",
        "total_tiles",
        "sliding_mean_score",
        "sliding_median_score",
        "sliding_p75_score",
        "sharp_window_fraction",
        "usable_pixel_fraction",
        "mask_coverage_fraction",
        "usable_windows",
        "sharp_windows",
        "total_windows",
        "percentile_within_project",
        "flag",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            formatted = dict(row)

            for key in [
                "sharpness_score",
                "tile_mean_score",
                "tile_median_score",
                "tile_p75_score",
                "sliding_mean_score",
                "sliding_median_score",
                "sliding_p75_score",
            ]:
                formatted[key] = f"{row[key]:.2f}"

            for key in [
                "sharp_tile_fraction",
                "sharp_window_fraction",
                "usable_pixel_fraction",
                "mask_coverage_fraction",
            ]:
                formatted[key] = f"{row[key]:.3f}"

            formatted["percentile_within_project"] = (
                f'{row["percentile_within_project"]:.2f}'
            )

            writer.writerow(formatted)

    if args.copy_review:
        review_root = Path(args.review_folder).expanduser().resolve()
        copied = 0

        for row in rows:
            if row["flag"] != "REVIEW":
                continue

            source = image_root / row["relative_path"]
            destination = review_root / row["relative_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

        print(f"Copied {copied:,} REVIEW images to: {review_root}")

    kept = sum(1 for row in valid_rows if row["flag"] == "KEEP")
    review = sum(1 for row in valid_rows if row["flag"] == "REVIEW")
    skipped = sum(1 for row in valid_rows if row["flag"] == "SKIP")

    print()
    print(f"CSV written to: {output}")
    print(f"COLMAP masks written to: {mask_root}")
    print(f"KEEP:   {kept:,}")
    print(f"REVIEW: {review:,}")
    print(f"SKIP:   {skipped:,}")
    print()
    print("COLMAP mask convention:")
    print("  WHITE = feature extraction allowed")
    print("  BLACK = feature extraction blocked")
    print("  Example: 000868_CAM02.jpg -> 000868_CAM02.jpg.png")
    print()
    print("Important:")
    print("  - Masks are saved at the original photograph dimensions.")
    print("  - Source photographs are never cropped, modified, or deleted.")
    print("  - SKIP means the final mask is entirely black.")
    print("  - REVIEW means some sharp area exists but covers less than the KEEP threshold.")
    print("  - KEEP images can still contain large masked regions; COLMAP receives the original image plus its mask.")


if __name__ == "__main__":
    main()
