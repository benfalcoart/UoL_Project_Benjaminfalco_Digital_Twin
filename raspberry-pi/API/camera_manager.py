from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

"""
Class representing the USB Camera on the Raspberry Pi.
"""
@dataclass
class Camera:
    id: int
    device: str
    name: str
    active: bool = True

@dataclass
class CaptureAttempt:
    attempt: int
    success: bool
    return_code: int
    error: str | None = None

"""
Resulting capture of the camera
"""
@dataclass
class CaptureResult:
    camera: Camera
    success: bool
    output_path: Path
    attempts: list[CaptureAttempt]

class CameraManager:
    def __init__(self):
        self.cameras = self.discover_cameras()

    """
    Automatically search for all camera devices that are plugged in so that system can be scaled up or down.
    """
    def discover_cameras(self) -> list[Camera]:
        cameras = []

        video_devices = sorted(Path("/dev").glob("video*"), key=lambda path: int(path.name.replace("video","")))

        for device in video_devices:
            command = [
                "v4l2-ctl",
                f"--device={device}",
                "--list-formats-ext"        
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
            except subprocess.TimeoutExpired:
                continue

            if result.returncode != 0:
                continue

            if "'MJPG'" not in result.stdout:
                continue

            if "1920x1080" not in result.stdout:
                continue

            camera_id = len(cameras) + 1

            cameras.append(
                Camera(
                    id=camera_id,
                    device=str(device),
                    name=f"Camera {camera_id}",
                    active=True
                )
            )

        return cameras

    """
    Capture photos from all Cameras at once. Using MultiThreading so camera captures are concurrent.
    """
    def capture_all(self, output_directory: Path) -> list[CaptureResult]:
        #exit early if no cameras connected or no cameras are active.
        if self.get_number_active_cameras() == 0:
            return []

        output_directory.mkdir(parents=True, exist_ok=True)
        results = []
        #begin mutli threading to take pictures cocurrently.
        with ThreadPoolExecutor(max_workers=self.get_number_active_cameras()) as executor:
            futures = {}

            for camera in self.get_active_cameras():
                output_path = output_directory / f"cam_{camera.id:02d}.jpg"

                future = executor.submit(
                    self.capture_camera,
                    camera,
                    output_path
                )

                futures[future] = camera

            for future in as_completed(futures):
                camera = futures[future]

                try:
                    results.append(future.result())
                except Exception as error:
                    results.append(
                        CaptureResult(camera=camera, success=False, output_path=output_directory / f"cam_{camera.id:02d}.jpg",
                            attempts=[CaptureAttempt(attempt=0, success=False, return_code=-1, error=str(error))]
                        )
                    )

            return results

    def capture_camera(self, camera: Camera, output_path: Path, retries: int = 3, timeout: float = 5.0) -> CaptureResult:

        #Create the camera's destination path.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not camera.active:
            return CaptureResult(camera=camera, success=False, output_path=output_path,attempts=[])

        attempts = []
        #attempt to take a photo
        for attempt in range(1, retries + 1):
            if output_path.exists():
                output_path.unlink()

            command = [
                "v4l2-ctl",
                f"--device={camera.device}",
                "--set-fmt-video=width=1920,height=1080,pixelformat=MJPG",
                "--stream-mmap",
                "--stream-count=1",
                f"--stream-to={output_path}"
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                success = (result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0)
                attempts.append(CaptureAttempt(attempt=attempt, success=success, return_code=result.returncode, error=None if success else result.stderr.strip()))

                #if success, return the result.
                if success:
                    return CaptureResult(camera=camera, success=True, output_path=output_path, attempts=attempts)

            except subprocess.TimeoutExpired:
                attempts.append(CaptureAttempt(attempt=attempt, success=False, return_code=-1, error=f"Capture timed out after {timeout} seconds"))

            time.sleep(0.25)

        if output_path.exists():
            output_path.unlink()

        return CaptureResult(camera=camera, success=False, output_path=output_path, attempts=attempts)

    def get_active_cameras(self) -> list[Camera]:
        active_cameras = []
        for camera in self.cameras:
            if camera.active:
                active_cameras.append(camera)

        return active_cameras

    def get_number_active_cameras(self) -> int:        
        return len(self.get_active_cameras())

    def set_camera_active(self, camera_id: int, active: bool) -> bool:
        for camera in self.cameras:
            if camera.id == camera_id:
                camera.active = active
                return True

        return False

    def enable_camera(self, camera_id: int) -> bool:
        return self.set_camera_active(camera_id, True)


    def disable_camera(self, camera_id: int) -> bool:
        return self.set_camera_active(camera_id, False)