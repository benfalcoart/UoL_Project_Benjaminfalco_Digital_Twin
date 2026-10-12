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
    parser = argparse.ArgumentParser(description=("Analyze BEHOLDER COLMAP masks and report image-level usability plus aggregate white/black pixel coverage."))
    parser.add_argument("mask_root", help="Folder containing generated mask PNG files.",)
    parser.add_argument("--output", default="mask_ratio_report.csv", help="Per-mask CSV output. Default: mask_ratio_report.csv")

    parser.add_argument("--threshold", type=int, default=127, help="Pixels above this grayscale value count as white/usable. Default: 127")

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

        except Exception as exc:
            rows.append(
                {
                    "relative_path": str(path.relative_to(root)),
                    "width": 0,
                    "height": 0,
                    "total_pixels": 0,
                    "white_pixels": 0,
                    "black_pixels": 0,
                    "white_fraction": 0.0,
                    "black_fraction": 0.0,
                    "status": f"ERROR: {exc}",
                }
            )

        if index % 500 == 0 or index == len(masks):
            print(f"  {index:,}/{len(masks):,}")

    valid_rows = [row for row in rows if not row["status"].startswith("ERROR")]
    valid_images = len(valid_rows)
    usable_images = fully_usable + partial

    image_usable_fraction = (usable_images / valid_images if valid_images else 0.0)

    image_fully_masked_fraction = (fully_masked / valid_images if valid_images else 0.0)

    total_pixels = total_white + total_black

    aggregate_white_fraction = (total_white / total_pixels if total_pixels else 0.0)

    aggregate_black_fraction = (total_black / total_pixels if total_pixels else 0.0)

    if white_fractions:
        mean_white_fraction = float(np.mean(white_fractions))
        median_white_fraction = float(np.median(white_fractions))
        p25_white_fraction = float(np.percentile(white_fractions, 25))
        p75_white_fraction = float(np.percentile(white_fractions, 75))
    else:
        mean_white_fraction = 0.0
        median_white_fraction = 0.0
        p25_white_fraction = 0.0
        p75_white_fraction = 0.0

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file,fieldnames=[
                "relative_path",
                "width",
                "height",
                "total_pixels",
                "white_pixels",
                "black_pixels",
                "white_fraction",
                "black_fraction",
                "status",
            ],
        )

        writer.writeheader()

        for row in rows:
            formatted = dict(row)

            if isinstance(formatted["white_fraction"], float):
                formatted["white_fraction"] = f'{formatted["white_fraction"]:.6f}'

            if isinstance(formatted["black_fraction"], float):
                formatted["black_fraction"] = f'{formatted["black_fraction"]:.6f}'

            writer.writerow(formatted)

    print()
    print("=" * 72)
    print("BEHOLDER MASK ANALYSIS")
    print("=" * 72)
    print(f"Mask folder:              {root}")
    print(f"Total valid masks:        {valid_images:,}")
    print()
    print("IMAGE-LEVEL USABILITY")
    print(f"Usable images:            {usable_images:,} ({image_usable_fraction:.2%})")
    print(f"Fully masked images:      {fully_masked:,} ({image_fully_masked_fraction:.2%})")
    print(f"Partially usable images:  {partial:,}")
    print(f"Fully usable images:      {fully_usable:,}")
    print()
    print("PIXEL-LEVEL MASK COVERAGE")
    print(f"Aggregate white pixels:   {aggregate_white_fraction:.2%}")
    print(f"Aggregate black pixels:   {aggregate_black_fraction:.2%}")
    print(f"Mean white coverage/img:  {mean_white_fraction:.2%}")
    print(f"Median white coverage:    {median_white_fraction:.2%}")
    print(f"25th percentile:          {p25_white_fraction:.2%}")
    print(f"75th percentile:          {p75_white_fraction:.2%}")
    print()
    print(f"Per-mask CSV written to:  {output}")
    print()
    print("REPORT-SAFE SUMMARY")
    print(f"{image_usable_fraction:.1%} of captured images retained at least some "
        "usable image area after sliding-window Laplacian blur analysis, while "
        f"{image_fully_masked_fraction:.1%} were fully masked and excluded from "
        "COLMAP feature extraction."
    )
    print(f"Across all masks, {aggregate_white_fraction:.1%} of image pixels remained "
        "available for feature extraction and "
        f"{aggregate_black_fraction:.1%} were masked."
    )


if __name__ == "__main__":
    main()
