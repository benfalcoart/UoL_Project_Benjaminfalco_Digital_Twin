from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
import subprocess
import time



"""
Represents the physical camera slots on the Beholder Case. Will need to be manually calibrated.
"""
class CameraSlot(Enum):
    UNASSIGNED = "unassigned"

    TOP = "T1"

    UPPER_1 = "U1"
    UPPER_2 = "U2"
    UPPER_3 = "U3"
    UPPER_4 = "U4"
    UPPER_5 = "U5"

    MIDDLE_1 = "M1"
    MIDDLE_2 = "M2"
    MIDDLE_3 = "M3"
    MIDDLE_4 = "M4"
    MIDDLE_5 = "M5"
    MIDDLE_6 = "M6"
    MIDDLE_7 = "M7"
    MIDDLE_8 = "M8"
    MIDDLE_9 = "M9"

    LOWER_1 = "L1"
    LOWER_2 = "L2"
    LOWER_3 = "L3"
    LOWER_4 = "L4"
    LOWER_5 = "L5"

    BOTTOM = "B1"

@dataclass
class Camera:
    id: int
    device: str
    name: str
    active: bool = True
    slot: CameraSlot = CameraSlot.UNASSIGNED

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

CAMERA_CONTROLS = {
    "brightness",
    "contrast",
    "saturation",
    "hue",
    "white_balance_automatic",
    "gamma",
    "gain",
    "power_line_frequency",
    "white_balance_temperature",
    "sharpness",
    "backlight_compensation",
    "auto_exposure",
    "exposure_time_absolute",
    "exposure_dynamic_framerate"
}

"""
Class representing the USB Camera on the Raspberry Pi.
"""
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

            cameras.append(Camera(id=camera_id, device=str(device), name=f"Camera {camera_id}", active=True))

        return cameras

    """
    Get Camera by ID.
    """
    def get_camera(self, camera_id: int) -> Camera | None:
        for camera in self.cameras:
            if camera.id == camera_id:
                return camera

        return None
    """
    Get the current Camera settings
    """
    def get_camera_settings(self, camera_id: int) -> dict | None:
        camera = self.get_camera(camera_id)

        if camera is None:
            return None

        controls = ",".join(CAMERA_CONTROLS)
        command = ["v4l2-ctl", f"--device={camera.device}", f"--get-ctrl={controls}"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        settings = {}

        for line in result.stdout.splitlines():
            if ":" not in line:
                continue

            name, value = line.split(":", 1)
            settings[name.strip()] = int(value.strip().split()[0])

        return settings
    """
    Get all camera Settings
    """
    def get_all_camera_settings(self) -> dict:
        results = {}

        for camera in self.cameras:
            try:
                settings = self.get_camera_settings(camera.id)
                results[camera.id] = settings
            except Exception as error:
                results[camera.id] = {
                    "error": str(error)
                }

        return results
    """
    Helper made to identify a camera on client app.
    """
    def identify_camera(self, camera_id: int) -> CaptureResult | None:
        camera = self.get_camera(camera_id)

        if camera is None:
            return None

        output_path = Path(f"/tmp/beholder_identify_camera_{camera_id:02d}.jpg")
        return self.capture_camera(camera, output_path, retries=1, timeout=5.0, allow_inactive=True)
    """
    Set Camera Settings by camera ID
    """
    def set_camera_setting(self, camera_id: int, setting: str, value: int) -> bool:
        camera = self.get_camera(camera_id)

        if camera is None:
            return False

        if setting not in CAMERA_CONTROLS:
            raise ValueError(f"Unsupported camera setting: {setting}")

        command = ["v4l2-ctl", f"--device={camera.device}", f"--set-ctrl={setting}={value}"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        return True

    """
    Sets all the camera settings.
    """
    def set_all_camera_settings(self, setting: str, value: int) -> dict:
        if setting not in CAMERA_CONTROLS:
            raise ValueError(f"Unsupported camera setting: {setting}")        
        results = {}

        for camera in self.cameras:
            try:
                success = self.set_camera_setting(camera.id, setting, value)
                results[camera.id] = success
            except Exception:
                results[camera.id] = False

        return results

    """
    Set camera to specific slot. Only 1 slot can be occupied at a time.
    """
    def set_camera_slot(self, camera_id: int, slot_value: str) -> bool:
        camera = self.get_camera(camera_id)

        if camera is None:
            return False

        try:
            slot = CameraSlot(slot_value)
        except ValueError:
            return False

        if slot != CameraSlot.UNASSIGNED:
            for current_camera in self.cameras:
                if (
                    current_camera.id != camera_id
                    and current_camera.slot == slot
                ):
                    return False

        camera.slot = slot
        return True

    """
    Capture photos from all Cameras at once. Using MultiThreading so camera captures are concurrent.
    """
    def capture_all(self, output_directory: Path, capture_id: int, retries: int = 3, timeout: float = 5.0) -> list[CaptureResult]:
        #exit early if no cameras connected or no cameras are active.
        if self.get_number_active_cameras() == 0:
            return []

        output_directory.mkdir(parents=True, exist_ok=True)
        results = []
        #begin mutli threading to take pictures cocurrently.
        with ThreadPoolExecutor(max_workers=self.get_number_active_cameras()) as executor:
            futures = {}

            for camera in self.get_active_cameras():
                output_path = output_directory / f"{capture_id:06d}_CAM{camera.id:02d}.jpg"

                future = executor.submit(self.capture_camera, camera, output_path, retries, timeout)
                futures[future] = camera

            for future in as_completed(futures):
                camera = futures[future]

                try:
                    results.append(future.result())
                except Exception as error:
                    results.append(
                        CaptureResult(camera=camera, success=False, output_path=output_directory / f"{capture_id:06d}_CAM{camera.id:02d}.jpg",
                            attempts=[CaptureAttempt(attempt=0, success=False, return_code=-1, error=str(error))]
                        )
                    )

            return results

    def capture_camera(self, camera: Camera, output_path: Path, retries: int = 3, timeout: float = 5.0, allow_inactive: bool = False) -> CaptureResult:

        #Create the camera's destination path.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not camera.active and not allow_inactive:
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

            if attempt < retries:
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

    def set_camera_active(self, camera_id_or_slot: int | CameraSlot, active: bool) -> bool:
        for current_camera in self.cameras:
            if isinstance(camera_id_or_slot, int) and current_camera.id == camera_id_or_slot:
                current_camera.active = active
                return True

            if isinstance(camera_id_or_slot, CameraSlot) and current_camera.slot == camera_id_or_slot:
                current_camera.active = active
                return True

        return False
    
    def enable_camera(self, camera_id_or_slot: int | CameraSlot) -> bool:
        return self.set_camera_active(camera_id_or_slot, True)

    def disable_camera(self, camera_id_or_slot: int | CameraSlot) -> bool:
        return self.set_camera_active(camera_id_or_slot, False)
