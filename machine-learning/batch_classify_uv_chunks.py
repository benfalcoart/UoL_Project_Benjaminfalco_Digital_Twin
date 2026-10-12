"""Classify baked UV chunks in photogrammetry-scans/*_ml_ready, optionally with a priority CSV.

Place alongside classify-UV-crop-superpixel-sliding-window.py in machine-learning/.

Examples (from machine-learning/):
    python -u batch_classify_uv_chunks.py --only Tree_Cleaned_ml_ready --limit 1 --models minc
    python -u batch_classify_uv_chunks.py --only Tree_Cleaned_ml_ready --models minc matsynth dms --method soft --topology
    python -u batch_classify_uv_chunks.py --models minc matsynth dms --method soft --topology
    python -u batch_classify_uv_chunks.py --all-configurations  # three singles + triple, soft only
    python -u batch_classify_uv_chunks.py --queue reconstruction_queue.csv --all-configurations --ensemble-first --topology

Requires a classifier accepting --reconstruction, --diffuse, --mask, --models,
--method and emitting material_id_superpixel_merged.png, topology_segments.npz,
and topology_regions.json for each chunk.
"""

import argparse
import csv
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


MODEL_CHOICES = ("minc", "matsynth", "dms", "minc_legacy")
DEFAULT_MODELS = ("minc", "matsynth", "dms")
REQUIRED_OUTPUTS = ("material_id_superpixel_merged.png", "topology_segments.npz", "topology_regions.json")


def play_completion_sound(success):
    """Play a distinct completion/failure melody on Windows without failing the batch."""
    if sys.platform != "win32":
        print("Completion sound is only available on Windows.", flush=True)
        return

    try:
        import winsound
        notes = [(659, 180), (784, 180), (988, 220), (1319, 650)] if success else [(440, 400), (330, 400), (220, 700), (220, 700)]
        for frequency, duration in notes:
            winsound.Beep(frequency, duration)
            time.sleep(0.10)
    except (OSError, RuntimeError) as exc:
        print(f"Could not play completion sound: {exc}", flush=True)


def discover_folders(root, only=None, input_dir=None):
    if input_dir is not None:
        folders = [input_dir.resolve()]
    else:
        if not root.is_dir():
            raise FileNotFoundError(f"Missing scan root: {root}")
        folders = sorted(p for p in root.iterdir() if p.is_dir() and p.name.lower().endswith("_ml_ready"))

    if only:
        folders = [p for p in folders if p.name.casefold() == only.casefold()]
    if not folders:
        raise ValueError(f"No matching reconstructions. Root: {root}; --only: {only}")
    if any(not p.is_dir() for p in folders):
        raise FileNotFoundError("One of the selected reconstruction folders does not exist")
    if len({p.name.casefold() for p in folders}) != len(folders):
        raise ValueError("Duplicate reconstruction names would collide in the outputs folder")
    return folders



def read_reconstruction_queue(queue_path, scan_root):
    """Read reconstruction names in CSV row order, without discovering every folder."""
    if not queue_path.is_file():
        raise FileNotFoundError(f"Queue CSV not found: {queue_path}")
    if not scan_root.is_dir():
        raise FileNotFoundError(f"Scan root not found: {scan_root}")

    with queue_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(rows)
        if not reader.fieldnames:
            raise ValueError(f"Queue CSV has no header: {queue_path}")
        headers = {header.strip().lower(): header for header in reader.fieldnames if header}
        name_column = headers.get("reconstruction") or headers.get("folder")
        enabled_column = headers.get("enabled")
        if name_column is None:
            raise ValueError("Queue CSV must contain a 'reconstruction' (or 'folder') column")

        folders = []
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            name = (row.get(name_column) or "").strip()
            enabled = (row.get(enabled_column) or "").strip().casefold() if enabled_column else "1"
            if enabled in ("0", "false", "no", "off", "skip"):
                continue
            if enabled not in ("", "1", "true", "yes", "on"):
                raise ValueError(f"Invalid 'enabled' value on queue row {line_number}: {enabled!r}")
            if not name:
                raise ValueError(f"Empty reconstruction name on queue row {line_number}")
            if name.casefold() in seen:
                raise ValueError(f"Duplicate reconstruction in queue: {name}")
            # Only accept direct child folder names: not arbitrary paths or traversal.
            folder = (scan_root / name).resolve()
            if folder.parent != scan_root or not folder.is_dir():
                raise FileNotFoundError(f"Queue row {line_number} does not refer to a folder directly under {scan_root}: {name}")
            if not folder.name.lower().endswith("_ml_ready"):
                raise ValueError(f"Queue row {line_number} is not an _ml_ready folder: {name}")
            seen.add(name.casefold())
            folders.append(folder)

    if not folders:
        raise ValueError(f"Queue CSV contains no enabled reconstructions: {queue_path}")
    return folders

def discover_chunks(folder):
    chunks = []
    for sidecar in sorted(folder.glob("chunk_*_ml_uv.npz")):
        name = sidecar.name.removesuffix("_ml_uv.npz")
        diffuse = folder / f"{name}.png"
        if not diffuse.is_file():
            raise FileNotFoundError(f"Missing baked diffuse image: {diffuse}")
        chunks.append((name, diffuse, sidecar))
    if not chunks:
        raise FileNotFoundError(f"No chunk_*_ml_uv.npz files in {folder}")
    return chunks


def generate_uv_mask(sidecar_path, diffuse_path, mask_path, force=False):
    if mask_path.is_file() and not force and mask_path.stat().st_mtime >= sidecar_path.stat().st_mtime:
        with Image.open(mask_path) as old, Image.open(diffuse_path) as diffuse:
            if old.size == diffuse.size:
                return False

    with np.load(sidecar_path, allow_pickle=False) as data:
        triangles = data["triangle_pixels"]
        texture_size = int(np.asarray(data["texture_size"]).flat[0])

    with Image.open(diffuse_path) as diffuse:
        width, height = diffuse.size
    if (width, height) != (texture_size, texture_size):
        raise ValueError(f"Texture and UV metadata sizes differ in {sidecar_path.name}: {(width, height)} vs {texture_size}")
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 2):
        raise ValueError(f"Unexpected triangle_pixels array in {sidecar_path.name}: {triangles.shape}")

    mask = np.zeros((height, width), dtype=np.uint8)
    for triangle in triangles:
        if np.isfinite(triangle).all():
            cv2.fillConvexPoly(mask, np.rint(triangle).astype(np.int32), 255)
    if not np.any(mask):
        raise ValueError(f"Mask is empty: {sidecar_path}")

    mask_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(mask_path), mask):
        raise OSError(f"Could not save mask: {mask_path}")
    return True


def configurations(args):
    if args.all_configurations:
        # Three single-model baselines plus one three-model soft ensemble.
        # No pairwise ensembles or hard voting.
        single_models = [([model], "soft") for model in DEFAULT_MODELS]
        triple_ensemble = (list(DEFAULT_MODELS), "soft")
        if args.ensemble_first:
            yield triple_ensemble
            yield from single_models
        else:
            yield from single_models
            yield triple_ensemble
    else:
        yield list(dict.fromkeys(args.models)), "soft"


def check_classifier(classifier):
    if not classifier.is_file():
        raise FileNotFoundError(f"Classifier not found: {classifier}")
    help_result = subprocess.run([sys.executable, str(classifier), "--help"], capture_output=True, text=True)
    required_args = ("--models", "--method", "--reconstruction", "--diffuse", "--mask")
    if help_result.returncode != 0 or any(arg not in help_result.stdout for arg in required_args):
        raise RuntimeError("The classifier must support --models, --method, --reconstruction, --diffuse and --mask.\n" + help_result.stdout + help_result.stderr)


def run_job(cmd, base_dir):
    print("  Command:", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=base_dir, check=True)


def main():
    base_dir = Path(__file__).resolve().parent
    default_root = base_dir.parent / "photogrammetry-scans"
    parser = argparse.ArgumentParser(description="Batch classify UV chunks in *_ml_ready folders, optionally using an ordered CSV queue")
    parser.add_argument("--scan-root", type=Path, default=default_root, help="Parent folder of *_ml_ready directories")
    parser.add_argument("--queue", type=Path, help="CSV of reconstruction folder names, processed top to bottom (relative to this script)")
    parser.add_argument("--input-dir", type=Path, help="Process one folder elsewhere instead of scanning --scan-root")
    parser.add_argument("--only", help="Process just this exact reconstruction folder name (e.g. Tree_Cleaned_ml_ready)")
    parser.add_argument("--models", nargs="+", choices=MODEL_CHOICES, default=list(DEFAULT_MODELS))
    parser.add_argument("--method", choices=("soft",), default="soft", help="Soft probability averaging only; hard voting is disabled")
    parser.add_argument("--all-configurations", action="store_true", help="Run four soft configurations: MINC, MatSynth, DMS, then their three-model ensemble")
    parser.add_argument("--ensemble-first", action="store_true", help="With --all-configurations, run the three-model soft ensemble before the single-model baselines")
    parser.add_argument("--limit", type=int, help="Process only the first N chunks per reconstruction (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="List planned work, without changing any files")
    parser.add_argument("--masks-only", action="store_true", help="Generate UV masks but do not classify")
    parser.add_argument("--topology", action="store_true", help="After all chunks are classified, refine using shared mesh triangle edges")
    parser.add_argument("--force", action="store_true", help="Rerun completed classifications and topology refinement")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop at the first error instead of moving on")
    parser.add_argument("--no-beep", action="store_true", help="Disable the completion/error sound")
    args = parser.parse_args()

    if args.queue and (args.only or args.input_dir):
        parser.error("--queue cannot be combined with --only or --input-dir")
    if args.ensemble_first and not args.all_configurations:
        parser.error("--ensemble-first requires --all-configurations")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.topology and args.masks_only:
        parser.error("--topology cannot be used with --masks-only")

    classifier = base_dir / "classify-UV-crop-superpixel-sliding-window.py"
    refiner = base_dir / "mesh_topology_refine.py"
    try:
        scan_root = args.scan_root.resolve()
        queue_path = (base_dir / args.queue).resolve() if args.queue else None
        folders = read_reconstruction_queue(queue_path, scan_root) if queue_path else discover_folders(scan_root, args.only, args.input_dir)
        configs = list(configurations(args))
        if not args.dry_run and not args.masks_only:
            check_classifier(classifier)
        if args.topology and not args.dry_run and not refiner.is_file():
            raise FileNotFoundError(f"Topology refiner not found: {refiner}")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    print(f"Started: {datetime.now().isoformat(timespec='seconds')}", flush=True)
    print(f"Scan root: {args.scan_root.resolve()}", flush=True)
    if args.queue:
        print(f"CSV queue (priority order): {queue_path}", flush=True)
    print(f"Reconstructions: {len(folders)}, configurations: {len(configs)}", flush=True)
    print(f"Outputs: {base_dir / 'outputs'}", flush=True)
    start_time = time.monotonic()
    completed = skipped = failed = 0

    for folder_index, folder in enumerate(folders, start=1):
        name = folder.name
        try:
            chunks = discover_chunks(folder)
        except Exception as exc:
            failed += 1
            print(f"ERROR discovering {name}: {exc}", flush=True)
            if args.stop_on_error:
                break
            continue
        selected = chunks[:args.limit] if args.limit else chunks
        print(f"\n=== Reconstruction {folder_index}/{len(folders)}: {name} ({len(chunks)} chunks) ===", flush=True)

        for models, method in configs:
            config_name = "_".join(sorted(models)) + "_" + method
            out_root = base_dir / "outputs" / "superpixel" / name / config_name
            mask_root = base_dir / "outputs" / "uv_masks" / name
            print(f"\n--- Models: {', '.join(models)} | method: {method} ---", flush=True)
            errors_here = 0
            for chunk_index, (chunk_name, diffuse, sidecar) in enumerate(selected, start=1):
                output_dir = out_root / chunk_name
                required = [output_dir / filename for filename in REQUIRED_OUTPUTS]
                is_complete = all(p.is_file() for p in required)
                mask_path = mask_root / f"{chunk_name}_uv_mask.png"
                print(f"[{chunk_index}/{len(selected)}] {chunk_name}: ", end="", flush=True)
                if args.dry_run:
                    print("SKIP (already complete)" if is_complete and not args.force else "WOULD RUN", flush=True)
                    continue
                try:
                    if is_complete and not args.force and not args.masks_only:
                        print("SKIP (already complete)", flush=True)
                        skipped += 1
                        continue
                    created = generate_uv_mask(sidecar, diffuse, mask_path, args.force)
                    print("mask generated" if created else "mask reused", flush=True)
                    if args.masks_only:
                        completed += 1
                        continue
                    cmd = [sys.executable, "-u", str(classifier), "--models", *models, "--method", method, "--reconstruction", name, "--diffuse", str(diffuse), "--mask", str(mask_path)]
                    run_job(cmd, base_dir)
                    if not all(p.is_file() for p in required):
                        missing = [p.name for p in required if not p.is_file()]
                        raise RuntimeError(f"Classifier returned without required outputs: {missing}. Check that topology exports were added to the classifier.")
                    completed += 1
                    print(f"  COMPLETED: {chunk_name}", flush=True)
                except Exception as exc:
                    errors_here += 1
                    failed += 1
                    print(f"  ERROR: {exc}", flush=True)
                    traceback.print_exc()
                    if args.stop_on_error:
                        break

            if args.topology and not args.dry_run and not args.masks_only and args.limit is None and errors_here == 0:
                topology_path = folder / "global_mesh_topology.npz"
                topology_outputs = [out_root / chunk_name / "material_id_topology_refined.png" for chunk_name, _, _ in chunks]
                topology_outputs.append(out_root / "topology_changes.csv")
                if not topology_path.is_file():
                    failed += 1
                    print(f"ERROR: missing topology file: {topology_path}", flush=True)
                elif all(p.is_file() for p in topology_outputs) and not args.force:
                    print("Topology: SKIP (already complete)", flush=True)
                elif not all((out_root / chunk_name / filename).is_file() for chunk_name, _, _ in chunks for filename in REQUIRED_OUTPUTS):
                    print("Topology: postponed (not all chunks have classification results)", flush=True)
                else:
                    try:
                        cmd = [sys.executable, "-u", str(refiner), "--topology", str(topology_path), "--chunks-dir", str(folder), "--results-dir", str(out_root), "--edge-samples", "5"]
                        print("Topology: processing shared triangle edges", flush=True)
                        run_job(cmd, base_dir)
                        if not all(p.is_file() for p in topology_outputs):
                            raise RuntimeError("Refiner returned without all output files")
                    except Exception as exc:
                        failed += 1
                        print(f"Topology ERROR: {exc}", flush=True)
                        traceback.print_exc()

            if args.stop_on_error and (errors_here or failed):
                break
        if args.stop_on_error and failed:
            break

    elapsed = (time.monotonic() - start_time) / 60
    print(f"\nFinished: {datetime.now().isoformat(timespec='seconds')}", flush=True)
    print(f"Duration: {elapsed:.1f} min | Classified/generated: {completed} | Skipped: {skipped} | Errors: {failed}", flush=True)
    if not args.dry_run and not args.no_beep:
        play_completion_sound(success=(failed == 0))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBatch interrupted.", flush=True)
        if "--no-beep" not in sys.argv and "--dry-run" not in sys.argv:
            play_completion_sound(success=False)
        raise SystemExit(130)
