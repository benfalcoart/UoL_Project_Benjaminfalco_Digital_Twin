import json
import re
from pathlib import Path

from API.camera_manager import CAMERA_CONTROLS, CameraManager

#The order in which the settings change is important so this will be the order they are changed in:
PROFILE_SETTING_ORDER = [
    "auto_exposure",
    "white_balance_automatic",
    "exposure_dynamic_framerate",
    "exposure_time_absolute",
    "gain",
    "white_balance_temperature",
    "brightness",
    "contrast",
    "saturation",
    "hue",
    "gamma",
    "sharpness",
    "backlight_compensation",
    "power_line_frequency"
]

class CameraProfileManager:
    def __init__(self, camera_manager: CameraManager, profile_directory: Path):
        self.camera_manager = camera_manager
        self.profile_directory = profile_directory
        self.profile_directory.mkdir(parents=True, exist_ok=True)

    def get_profiles(self) -> list[dict]:
        profiles = []

        for path in sorted(self.profile_directory.glob("*.json")):
            try:
                profile = self._load_profile_file(path)

                profiles.append({
                    "name": profile["name"],
                    "description": profile.get("description", ""),
                    "fileName": path.name
                })
            except Exception:
                continue

        return profiles

    def get_profile(self, profile_name: str) -> dict:
        path = self._get_profile_path(profile_name)

        if not path.exists():
            raise FileNotFoundError(f"Camera profile '{profile_name}' does not exist.")

        return self._load_profile_file(path)

    def save_profile(self, name: str, description: str, settings: dict) -> dict:
        self._validate_settings(settings)

        profile = {
            "name": name,
            "description": description,
            "settings": settings
        }

        path = self._get_profile_path(name)

        with path.open("w", encoding="utf-8") as file:
            json.dump(profile, file, indent=4)

        return profile

    def delete_profile(self, profile_name: str) -> bool:
        path = self._get_profile_path(profile_name)

        if not path.exists():
            return False

        path.unlink()
        return True

    def apply_profile(self, profile_name: str) -> dict:
        profile = self.get_profile(profile_name)
        settings = profile["settings"]
        results = {}

        for setting in PROFILE_SETTING_ORDER:
            if setting not in settings:
                continue

            results[setting] = self.camera_manager.set_all_camera_settings(setting, settings[setting])

        return results

    def save_current_settings(self, name: str, description: str = "") -> dict:
        camera_settings = self.camera_manager.get_all_camera_settings()

        if not camera_settings:
            raise RuntimeError("No cameras are available!")

        first_camera_id = next(iter(camera_settings))
        settings = camera_settings[first_camera_id]

        if "error" in settings:
            raise RuntimeError(settings["error"])

        return self.save_profile(name, description, settings)

    def _load_profile_file(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as file:
            profile = json.load(file)

        if "name" not in profile:
            raise ValueError(f"Profile '{path.name}' does not contain a name!")

        if "settings" not in profile:
            raise ValueError(f"Profile '{path.name}' does not contain settings!")

        self._validate_settings(profile["settings"])
        return profile

    def _validate_settings(self, settings: dict):
        for setting in settings:
            if setting not in CAMERA_CONTROLS:
                raise ValueError(f"Unsupported camera setting: {setting}")

            if not isinstance(settings[setting], int):
                raise ValueError(f"Camera setting '{setting}' must contain an integer value!")

    def _get_profile_path(self, profile_name: str) -> Path:
        file_name = self._get_safe_file_name(profile_name)
        return self.profile_directory / f"{file_name}.json"

    def _get_safe_file_name(self, profile_name: str) -> str:
        file_name = profile_name.strip().lower()
        #https://stackoverflow.com/questions/1721602/regex-for-matching-a-z-a-z-0-9-and
        file_name = re.sub(r"[^a-z0-9_-]+", "_", file_name)
        file_name = file_name.strip("_")

        if not file_name:
            raise ValueError("Profile name is invalid.")

        return file_name