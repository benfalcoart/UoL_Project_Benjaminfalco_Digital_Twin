import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from API.camera_manager import CameraManager
from API.camera_profile_manager import CameraProfileManager


def main():
    print("Creating CameraManager...")
    camera_manager = CameraManager()

    if len(camera_manager.cameras) == 0:
        print("No cameras detected.")
        return

    print(f"Detected {len(camera_manager.cameras)} camera(s).")

    test_directory = Path("/tmp/beholder_camera_profile_test")

    if test_directory.exists():
        shutil.rmtree(test_directory)

    profile_manager = CameraProfileManager(camera_manager, test_directory)

    print("\nReading original camera settings...")
    original_settings = camera_manager.get_all_camera_settings()

    first_camera_id = next(iter(original_settings))
    first_camera_settings = original_settings[first_camera_id]

    if "error" in first_camera_settings:
        raise RuntimeError(first_camera_settings["error"])

    original_frequency = first_camera_settings["power_line_frequency"]
    test_frequency = 2 if original_frequency != 2 else 1

    try:
        print("\n--- SAVE PROFILE TEST ---")

        profile_manager.save_profile(
            "Test Profile",
            "Temporary profile used by the automated test.",
            {
                "power_line_frequency": test_frequency
            }
        )

        profiles = profile_manager.get_profiles()

        for profile in profiles:
            print(f"Profile: {profile['name']}")

        if not any(profile["name"] == "Test Profile" for profile in profiles):
            raise RuntimeError("Saved profile was not found.")

        print("SAVE PROFILE TEST PASSED")

        print("\n--- LOAD PROFILE TEST ---")

        profile = profile_manager.get_profile("Test Profile")

        print(profile)

        if profile["settings"]["power_line_frequency"] != test_frequency:
            raise RuntimeError("Loaded profile contains the wrong value.")

        print("LOAD PROFILE TEST PASSED")

        print("\n--- APPLY PROFILE TEST ---")

        print(f"Original frequency: {original_frequency}")
        print(f"Applying test frequency: {test_frequency}")

        results = profile_manager.apply_profile("Test Profile")
        print(f"Apply results: {results}")

        updated_settings = camera_manager.get_all_camera_settings()

        for camera_id, settings in updated_settings.items():
            if "error" in settings:
                raise RuntimeError(f"Camera {camera_id}: {settings['error']}")

            actual_value = settings["power_line_frequency"]
            print(f"Camera {camera_id}: {actual_value}")

            if actual_value != test_frequency:
                raise RuntimeError(f"Camera {camera_id} did not receive the profile.")

        print("APPLY PROFILE TEST PASSED")

        print("\n--- SAVE CURRENT SETTINGS TEST ---")

        saved_profile = profile_manager.save_current_settings(
            "Current Settings Test",
            "Test of saving the current camera configuration."
        )

        if "settings" not in saved_profile:
            raise RuntimeError("Current settings profile was not created correctly.")

        print(f"Saved {len(saved_profile['settings'])} camera settings.")
        print("SAVE CURRENT SETTINGS TEST PASSED")

        print("\n--- DELETE PROFILE TEST ---")

        if not profile_manager.delete_profile("Test Profile"):
            raise RuntimeError("Unable to delete Test Profile.")

        if not profile_manager.delete_profile("Current Settings Test"):
            raise RuntimeError("Unable to delete Current Settings Test.")

        print("DELETE PROFILE TEST PASSED")

    finally:
        print("\nRestoring original camera settings...")

        for camera_id, settings in original_settings.items():
            if "error" in settings:
                continue

            original_value = settings["power_line_frequency"]
            camera_manager.set_camera_setting(camera_id, "power_line_frequency", original_value)
            print(f"Camera {camera_id}: restored to {original_value}")

        if test_directory.exists():
            shutil.rmtree(test_directory)

    print("\nALL CAMERA PROFILE TESTS PASSED")


if __name__ == "__main__":
    main()