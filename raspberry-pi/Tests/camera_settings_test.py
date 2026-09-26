import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from API.camera_manager import CameraManager

def main():
    print("Creating CameraManager...")
    camera_manager = CameraManager()

    print(f"Detected {len(camera_manager.cameras)} camera(s).")

    for camera in camera_manager.cameras:
        print(f"Camera {camera.id}: {camera.device}")

    camera_id = 1
    camera = camera_manager.get_camera(camera_id)

    if camera is None:
        print(f"Camera {camera_id} was not found.")
        return

    print(f"\nTesting Camera {camera_id} ({camera.device})")

    print("\nCurrent settings:")
    settings = camera_manager.get_camera_settings(camera_id)

    for name, value in settings.items():
        print(f"  {name}: {value}")

    original_frequency = settings["power_line_frequency"]

    try:
        print(f"\nOriginal power-line frequency: {original_frequency}")
        print("Setting power-line frequency to 60 Hz...")

        camera_manager.set_camera_setting(camera_id, "power_line_frequency", 2)

        updated_settings = camera_manager.get_camera_settings(camera_id)
        updated_frequency = updated_settings["power_line_frequency"]

        print(f"New power-line frequency: {updated_frequency}")

        if updated_frequency == 2:
            print("SET TEST PASSED")
        else:
            print("SET TEST FAILED")

    finally:
        print(f"\nRestoring original value: {original_frequency}")
        camera_manager.set_camera_setting(camera_id, "power_line_frequency", original_frequency)

        restored_settings = camera_manager.get_camera_settings(camera_id)
        restored_frequency = restored_settings["power_line_frequency"]

        print(f"Restored value: {restored_frequency}")

        if restored_frequency == original_frequency:
            print("RESTORE TEST PASSED")
        else:
            print("RESTORE TEST FAILED")


if __name__ == "__main__":
    main()
    