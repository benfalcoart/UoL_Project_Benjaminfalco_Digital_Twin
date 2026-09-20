from enum import Enum
import threading
import time


class CaptureMode(Enum):
    SINGLE = "single"
    AUTOMATIC = "automatic"


class CaptureController:
    def __init__(self, camera_manager, project_manager):
        self.camera_manager = camera_manager
        self.project_manager = project_manager

        self.mode = CaptureMode.SINGLE
        self.automatic_running = False
        self.capturing = False
        self.automatic_interval = 0.5

        self.automatic_thread = None
        self.capture_lock = threading.Lock()

    def set_mode(self, mode: CaptureMode):
        if self.automatic_running:
            self.stop_automatic()

        self.mode = mode

    def trigger(self):
        if self.mode == CaptureMode.SINGLE:
            if not self.capturing:
                threading.Thread(target=self.capture_once, daemon=True).start()

        elif self.mode == CaptureMode.AUTOMATIC:
            if self.automatic_running:
                self.stop_automatic()
            else:
                self.start_automatic()

    def capture_once(self, retries: int = 3, timeout: float = 5.0):
        project = self.project_manager.get_current_project()

        if project is None:
            return []

        if self.camera_manager.get_number_active_cameras() == 0:
            return []

        if not self.capture_lock.acquire(blocking=False):
            return []

        self.capturing = True

        try:
            capture_id = self.project_manager.get_next_capture_id()
            output_directory = project.directory / "images"

            results = self.camera_manager.capture_all(output_directory, capture_id, retries=retries, timeout=timeout)
            return results

        finally:
            self.capturing = False
            self.capture_lock.release()

    def start_automatic(self):
        if self.automatic_running:
            return

        if self.project_manager.get_current_project() is None:
            return

        if self.camera_manager.get_number_active_cameras() == 0:
            return

        self.automatic_running = True
        self.automatic_thread = threading.Thread(target=self._automatic_loop, daemon=True)
        self.automatic_thread.start()

    def stop_automatic(self):
        self.automatic_running = False

    def _automatic_loop(self):
        while self.automatic_running:
            start_time = time.monotonic()

            self.capture_once(retries=1, timeout=2.0)

            elapsed = time.monotonic() - start_time
            remaining = self.automatic_interval - elapsed

            if remaining > 0:
                time.sleep(remaining)

    def set_automatic_interval(self, seconds: float):
        if seconds <= 0:
            raise ValueError("Automatic capture interval must be greater than zero.")

        self.automatic_interval = seconds