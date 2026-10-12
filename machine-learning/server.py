"""BEHOLDER ML service: public model browsing; classification launching disabled.

Run from machine-learning/:
    python -m uvicorn server:app --host 127.0.0.1 --port 8001

Routes deliberately use /api/, NOT /api/ml/. Vite sends /api/volume to
port 8000 and all other /api requests to this service on port 8001.
"""

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="BEHOLDER Machine Learning API")

BEHOLDER_ROOT = Path(os.environ.get("BEHOLDER_DATA_ROOT", r"D:\BEHOLDER")).resolve()
SCANS_ROOT = BEHOLDER_ROOT / "photogrammetry_scans"
RESULTS_ROOT = BEHOLDER_ROOT / "superpixel"
CATALOG_PATH = BEHOLDER_ROOT / "reconstructions.json"
CATALOG_SCRIPT = BEHOLDER_ROOT / "generate_catalog.py"
BATCH_SCRIPT = Path(__file__).resolve().parent / "batch_classify_uv_chunks.py"
LOG_DIR = BEHOLDER_ROOT / "job_logs"

MATERIAL_MAP_FILES = {
    "material_id_superpixel_raw.png",
    "material_id_superpixel_merged.png",
    "material_id_tie_preview_raw.png",
    "material_id_topology_refined.png",
}

job_lock = threading.Lock()
jobs = {}  # In-memory registry; the ML server must remain running while a job executes.


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def deny_classification():
    """Fail closed for every caller; no token or other bypass exists.

    The implementation below is retained for future development, but neither
    the job-launch route nor its status route can execute until this dependency
    is intentionally replaced with an appropriate private authorization system.
    """
    raise HTTPException(status_code=403, detail="ML classification is disabled on this server")


class RunRequest(BaseModel):
    reconstruction: str
    topology: bool = True


@app.get("/api/ml/reconstructions")
def get_reconstructions():
    if not CATALOG_PATH.is_file():
        raise HTTPException(status_code=503, detail="Catalog not generated")
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Unable to read reconstruction catalog") from error


@app.get("/api/ml/model-files/{reconstruction}/{filename}")
def get_model_file(reconstruction: str, filename: str):
    if not filename.startswith("chunk_") or not filename.lower().endswith(".glb"):
        raise HTTPException(status_code=404, detail="Invalid model file")
    path = (SCANS_ROOT / reconstruction / filename).resolve()
    if path.parent.parent != SCANS_ROOT.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Model not found")
    return FileResponse(path, media_type="model/gltf-binary")


@app.get("/api/ml/material-maps/{reconstruction}/{configuration}/{chunk}/{filename}")
def get_material_map(reconstruction: str, configuration: str, chunk: str, filename: str):
    if filename not in MATERIAL_MAP_FILES:
        raise HTTPException(status_code=404, detail="Unsupported material map")
    path = (RESULTS_ROOT / reconstruction / configuration / chunk / filename).resolve()
    if path.parent.parent.parent.parent != RESULTS_ROOT.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Material map not found")
    return FileResponse(path, media_type="image/png")


def run_classification_job(job_id, command):
    """Run exactly one allowlisted classifier command in a worker thread."""
    log_path = LOG_DIR / f"{job_id}.log"
    return_code = None
    catalog_updated = False
    warning = None
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            log.write(f"Started: {utc_now()}\nCommand: {' '.join(command)}\n\n")
            log.flush()
            with job_lock:
                jobs[job_id]["status"] = "running"
            with subprocess.Popen(command, cwd=BATCH_SCRIPT.parent, stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT) as process:
                with job_lock:
                    jobs[job_id]["pid"] = process.pid
                return_code = process.wait()

            if return_code == 0 and CATALOG_SCRIPT.is_file():
                log.write("\nUpdating BEHOLDER reconstruction catalog...\n")
                log.flush()
                rebuild = subprocess.run([sys.executable, str(CATALOG_SCRIPT)], cwd=BEHOLDER_ROOT,
                                         capture_output=True, text=True, timeout=120)
                log.write(rebuild.stdout)
                log.write(rebuild.stderr)
                catalog_updated = rebuild.returncode == 0
                if not catalog_updated:
                    warning = "Classification finished, but catalog regeneration failed; run generate_catalog.py manually"
            elif return_code == 0:
                warning = "Classification finished; generate_catalog.py not found. Refresh catalog manually"
    except Exception as error:
        warning = f"Could not execute classification: {error}"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nERROR: {warning}\n")
    finally:
        with job_lock:
            job = jobs[job_id]
            job["status"] = "completed" if return_code == 0 else "failed"
            job["exit_code"] = return_code
            job["finished_at"] = utc_now()
            job["catalog_updated"] = catalog_updated
            job["warning"] = warning


@app.post("/api/ml/run", status_code=202, dependencies=[Depends(deny_classification)])
def start_classification(request: RunRequest):
    name = request.reconstruction
    # Exact, allowlisted names from the public catalog. Never accept filesystem paths.
    if not name or not name.lower().endswith("_ml_ready"):
        raise HTTPException(status_code=400, detail="Choose a processed *_ml_ready reconstruction")
    try:
        names = {entry["name"] for entry in get_reconstructions()["reconstructions"]}
    except (KeyError, TypeError) as error:
        raise HTTPException(status_code=500, detail="Invalid reconstruction catalog") from error
    folder = (SCANS_ROOT / name).resolve()
    if name not in names or folder.parent != SCANS_ROOT.resolve() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Reconstruction unavailable")
    if not BATCH_SCRIPT.is_file():
        raise HTTPException(status_code=503, detail="Batch classification script not found")
    if request.topology and not (folder / "global_mesh_topology.npz").is_file():
        raise HTTPException(status_code=422, detail="This reconstruction has no global_mesh_topology.npz; disable topology to proceed")

    # Fixed, non-shell command: three single ResNet18 models plus one soft ensemble.
    command = [sys.executable, "-u", str(BATCH_SCRIPT), "--scan-root", str(SCANS_ROOT),
               "--only", name, "--all-configurations", "--ensemble-first", "--no-beep"]
    if request.topology:
        command.append("--topology")

    with job_lock:
        if any(job["status"] in ("starting", "running") for job in jobs.values()):
            raise HTTPException(status_code=409, detail="Another ML classification job is already running")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        job_id = uuid4().hex
        jobs[job_id] = {"job_id": job_id, "reconstruction": name, "status": "starting",
                        "started_at": utc_now(), "finished_at": None, "exit_code": None,
                        "pid": None, "catalog_updated": False, "warning": None}
        threading.Thread(target=run_classification_job, args=(job_id, command), daemon=True).start()

    return {"job_id": job_id, "status": "starting", "message": "Four soft-only configurations queued for this reconstruction"}


@app.get("/api/ml/jobs/{job_id}", dependencies=[Depends(deny_classification)])
def job_status(job_id: str):
    with job_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Unknown job (jobs are not persisted across server restarts)")
        result = jobs[job_id].copy()
    log_path = LOG_DIR / f"{job_id}.log"
    if log_path.is_file():
        try:
            # Bound the response even if a classification writes gigabytes of logs.
            with log_path.open("rb") as log:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 4000))
                result["log_tail"] = log.read().decode("utf-8", errors="replace")
        except OSError:
            result["log_tail"] = ""
    else:
        result["log_tail"] = ""
    return result
