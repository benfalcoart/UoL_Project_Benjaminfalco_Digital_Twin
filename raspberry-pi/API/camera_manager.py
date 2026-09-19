from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

@dataclass
class Camera:
    id: int
    device: str
    name: str

@dataclass
class CaptureResult:
    camera: Camera
    success: bool
    output_path: Path
    attempts: int
    error: str | None = None

class CameraManager:
    def __init__(self):
        pass