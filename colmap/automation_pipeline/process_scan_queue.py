import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_enabled(value):
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def main():
    parser = argparse.ArgumentParser(description="Run multiple BEHOLDER projects sequentially through the masked reconstruction pipeline.")
    parser.add_argument("queue_csv", nargs="?", default="batch_projects.csv", help="CSV with columns project,enabled. Default: batch_projects.csv",)
    parser.add_argument("--clean", action="store_true", help="Pass --clean to each project.")
    parser.add_argument("--force-preprocess", action="store_true", help="Regenerate masks for every project.")
    parser.add_argument("--sharpness-threshold", type=float, default=30.0, help="Local Laplacian threshold for mask generation. Default: 30.")
    parser.add_argument("--workspace-root", default=r"D:\BEHOLDER_Processing", help=r"Root for reconstruction workspaces. Default: D:\BEHOLDER_Processing",)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    queue_path = Path(args.queue_csv).resolve()
    dual_script = script_dir / "process_scan_dual.py"

    if not queue_path.is_file():
        raise FileNotFoundError(f"Queue CSV not found: {queue_path}")

    if not dual_script.is_file():
        raise FileNotFoundError(f"Masked pipeline script not found: {dual_script}")

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    if not Path(workspace_root.anchor).is_dir():
        raise FileNotFoundError(f"Workspace drive is unavailable: {workspace_root.anchor}")
    workspace_root.mkdir(parents=True, exist_ok=True)

    with queue_path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    jobs = [row for row in rows if row.get("project", "").strip() and parse_enabled(row.get("enabled", "1"))]

    if not jobs:
        raise RuntimeError("No enabled projects were found in the queue CSV.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = script_dir / "batch_runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    queue_log = run_dir / "queue.log"
    summary_path = run_dir / "queue_summary.csv"

    def log(message=""):
        print(message)
        with queue_log.open("a", encoding="utf-8") as file:
            file.write(message + "\n")

    log("=" * 80)
    log("BEHOLDER PROJECT QUEUE")
    log("=" * 80)
    log(f"Queue: {queue_path}")
    log(f"Reconstruction workspace root: {workspace_root}")
    log(f"Sharpness threshold: {args.sharpness_threshold:g}")
    log(f"Enabled projects: {len(jobs)}")

    results = []

    for index, row in enumerate(jobs, start=1):
        project = row["project"].strip()

        log()
        log("=" * 80)
        log(f"PROJECT {index}/{len(jobs)} - {project}")
        log("=" * 80)

        command = [sys.executable, dual_script, project, "--workspace-root", workspace_root, "--sharpness-threshold", args.sharpness_threshold,]

        if args.clean:
            command.append("--clean")

        if args.force_preprocess:
            command.append("--force-preprocess")

        project_log = run_dir / f"project_{index:03d}.log"

        with project_log.open("w", encoding="utf-8") as out:
            out.write("> " + subprocess.list2cmdline([str(x) for x in command]) + "\n\n")
            out.flush()

            process = subprocess.Popen([str(x) for x in command], cwd=str(script_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,)

            assert process.stdout is not None

            for line in process.stdout:
                print(line.rstrip())
                out.write(line)
