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
        self.cameras = [
            Camera(1, "/dev/video0", "Camera 1"),
            Camera(2, "/dev/video1", "Camera 2"),
            Camera(3, "/dev/video4", "Camera 3"),
            Camera(4, "/dev/video6", "Camera 4"),
            Camera(5, "/dev/video8", "Camera 5"),
        ]

    def capture_camera(self, camera: Camera, output_path: Path, retries: int = 3) -> CaptureResult:
        #Create the camera's destination path.
        output_path.parent.mkdir(parents=True, exist_ok=True)

        last_error = None
        #attempt to take a photo
        for attempt in range(1, retries + 1):
            if output_path.exists():
                output_path.unlink()

            command = [
                f"--device={camera.device}",
                "--set-fmt-video=width=1920,height=1080,pixelformat=MJPG",
                "--stream-mmap",
                "--stream-count=1",
                f"--stream-to={output_path}"
            ]

            result = subprocess.run(command, capture_output=True, text=True)

            #if success, return the result.
            if result.returncode == 0:
                return CaptureResult(camera=camera, success=True, output_path=output_path, attempts=attempt)
            else:
                last_error = result.stderr.strip()
                time.sleep(0.25)