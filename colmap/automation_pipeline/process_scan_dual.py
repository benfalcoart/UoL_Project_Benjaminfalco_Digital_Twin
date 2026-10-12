import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class RunLogger:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message=""):
        print(message)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(message + "\n")


def run_logged(command, log_path, cwd=None):
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log:
        log.write("> " + subprocess.list2cmdline([str(x) for x in command]) + "\n\n")
        log.flush()

        process = subprocess.Popen([str(x) for x in command], cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,)

        assert process.stdout is not None

        for line in process.stdout:
            print(line.rstrip())
            log.write(line)

        return process.wait()


def find_images(images_path):
    return sorted(p for p in images_path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def mask_count(mask_path):
    return sum(1 for p in mask_path.rglob("*.png") if p.is_file()) if mask_path.is_dir() else 0


def parse_args():
    parser = argparse.ArgumentParser(description=("BEHOLDER end-to-end masked reconstruction: sliding-window masks, " "masked COLMAP/OpenMVS only."))
    parser.add_argument("project", help=r'Project relative to colmap\BEHOLDER_camera_offloads, e.g. "Basement\basement dark"',)
    parser.add_argument("--analysis-csv", help="Override blur-analysis CSV. Default: <project>\\beholder_blur_analysis.csv",)
    parser.add_argument("--force-preprocess", action="store_true", help="Regenerate masks/CSV even if a complete preprocessing result already exists.")
    parser.add_argument("--clean", action="store_true", help="Clean the masked reconstruction workspace before running it.")
    parser.add_argument("--workspace-root", default=r"D:\BEHOLDER_Processing", help=r"Root for reconstruction workspaces. Default: D:\BEHOLDER_Processing",)
    parser.add_argument("--use-gpu", action="store_true", help="Use COLMAP GPU SIFT if supported. Leave off on the current workstation.")
    parser.add_argument("--overlap", type=int, default=100)

    # Sliding-window defaults.
    parser.add_argument("--sharpness-threshold", type=float, default=30.0)
    parser.add_argument("--mask-vote-threshold", type=float, default=0.25)
    parser.add_argument("--min-keep-coverage", type=float, default=0.25)
    parser.add_argument("--window-size", type=int, default=192)
    parser.add_argument("--stride", type=int, default=64)
    parser.add_argument("--max-dimension", type=int, default=800)

    # Texture fallback controls.
    parser.add_argument("--mvs-decimate-start", type=float, default=1.0)
    parser.add_argument("--mvs-decimate-step", type=float, default=0.1)
    parser.add_argument("--mvs-decimate-min", type=float, default=0.1)
    parser.add_argument("--mvs-resolution-level", type=int, default=0)
    parser.add_argument("--mvs-max-texture-size", type=int, default=8192)

    return parser.parse_args()


def main():
    args = parse_args()

    if sys.platform != "win32":
        raise RuntimeError("This automation targets the Windows BEHOLDER processing workstation.")

    script_dir = Path(__file__).resolve().parent
    repo_colmap_dir = script_dir.parent
    offloads_root = repo_colmap_dir / "BEHOLDER_camera_offloads"

    project_path = (offloads_root / args.project).resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    if not Path(workspace_root.anchor).is_dir():
        raise FileNotFoundError(f"Workspace drive is unavailable: {workspace_root.anchor}")
    workspace_root.mkdir(parents=True, exist_ok=True)
    images_path = project_path / "images"
    masks_path = project_path / "masks"
    csv_path = Path(args.analysis_csv).resolve() if args.analysis_csv else project_path / "beholder_blur_analysis.csv"
    settings_path = project_path / "beholder_preprocess_settings.json"