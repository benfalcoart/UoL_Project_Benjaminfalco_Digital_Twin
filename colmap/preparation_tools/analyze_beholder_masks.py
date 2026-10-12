import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def find_masks(root: Path):
    return sorted(path for path in root.rglob("*.png") if path.is_file())


def analyze_mask(path: Path, threshold: int):
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    if mask is None:
        raise ValueError("OpenCV could not read the mask.")

    total_pixels = mask.size
    white_pixels = int(np.count_nonzero(mask > threshold))
    black_pixels = total_pixels - white_pixels

    white_fraction = white_pixels / total_pixels if total_pixels else 0.0
    black_fraction = black_pixels / total_pixels if total_pixels else 0.0

    if white_pixels == 0:
        status = "FULLY_MASKED"
    elif black_pixels == 0:
        status = "FULLY_USABLE"
    else:
        status = "PARTIAL"

    return {
        "width": mask.shape[1],
        "height": mask.shape[0],
        "total_pixels": total_pixels,
        "white_pixels": white_pixels,
        "black_pixels": black_pixels,
        "white_fraction": white_fraction,
        "black_fraction": black_fraction,
        "status": status,
    }


def main():
    parser = argparse.ArgumentParser(description=("Analyze BEHOLDER COLMAP masks and report image-level usability plus " "aggregate white/black pixel coverage."))

    parser.add_argument("mask_root", help="Folder containing generated mask PNG files.",)

    parser.add_argument("--output", default="mask_ratio_report.csv", help="Per-mask CSV output. Default: mask_ratio_report.csv",)

    parser.add_argument("--threshold", type=int, default=127, help="Pixels above this grayscale value count as white/usable. Default: 127",)

    args = parser.parse_args()

    root = Path(args.mask_root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not root.is_dir():
        raise SystemExit(f"Mask folder not found: {root}")

    masks = find_masks(root)

    if not masks:
        raise SystemExit(f"No PNG masks found under: {root}")

    rows = []

    total_white = 0
    total_black = 0
    fully_masked = 0
    fully_usable = 0
    partial = 0
    white_fractions = []

    for index, path in enumerate(masks, start=1):
        try:
            result = analyze_mask(path, args.threshold)

            row = {
                "relative_path": str(path.relative_to(root)),
                **result,
            }

            rows.append(row)

            total_white += result["white_pixels"]
            total_black += result["black_pixels"]
            white_fractions.append(result["white_fraction"])

            if result["status"] == "FULLY_MASKED":
                fully_masked += 1
            elif result["status"] == "FULLY_USABLE":
                fully_usable += 1
            else:
                partial += 1