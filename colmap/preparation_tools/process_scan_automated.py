import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

# BEHOLDER end-to-end reconstruction pipeline
# -------------------------------------------
# This script automates the workflow that was manually validated on the
# Niagara Railway Museum rail-car scan.
#
# Pipeline:
#   1. Read the blur-analysis CSV and choose usable images.
#      - Legacy CSV: only KEEP rows are used.
#      - Mask-aware CSV: KEEP and REVIEW rows with non-empty masks are used;
#        SKIP/DISCARD/ERROR rows are omitted.
#   2. Create one accepted-image list per physical BEHOLDER camera.
#   3. COLMAP feature extraction (one intrinsic group per camera), using
#      per-image feature masks when the CSV/mask folder provides them.
#   4. COLMAP sequential feature matching.
#   5. COLMAP sparse reconstruction (mapper).
#   6. COLMAP image undistortion / dense workspace preparation.
#   7. OpenMVS CUDA build: convert COLMAP -> MVS scene.
#   8. OpenMVS CUDA build: densify on CPU (the validated reliable setting).
#   9. OpenMVS CUDA build: reconstruct the dense mesh.
#  10. OpenMVS DEVELOP build: create a fresh scene and texture the mesh.
#  11. Export the final textured model directly as GLB for Blender/Three.js.
#
# The script records completed stages in pipeline_state.json. If a long run is
# interrupted, running the same command again will skip completed stages.

CAMERA_PATTERN = re.compile(r"_CAM(\d+)\.", re.IGNORECASE)
DRIVE_LETTERS = ["Z", "Y", "X", "W", "V", "U", "T", "S"]


def fresh_state():
    return {
        "features": {},
        "feature_signature": "",
        "matching": False,
        "matching_overlap": 0,
        "mapping": False,
        "undistort": False,
        "mvs_interface": False,
        "mvs_densify": False,
        "mvs_reconstruct": False,
        "mvs_dev_interface": False,
        "mvs_texture_glb": False,
    }


def slugify(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip())
    return value.strip("_").lower()


def load_state(path):
    state = fresh_state()
    if not path.exists():
        return state

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return state

    if isinstance(loaded.get("features"), dict):
        state["features"].update(loaded["features"])

    if isinstance(loaded.get("feature_signature"), str):
        state["feature_signature"] = loaded["feature_signature"]

    if isinstance(loaded.get("matching_overlap"), int):
        state["matching_overlap"] = loaded["matching_overlap"]

    for key in state:
        if key not in {"features", "feature_signature", "matching_overlap"} and isinstance(loaded.get(key), bool):
            state[key] = loaded[key]

    return state


def save_state(path, state):
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


class Logger:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)