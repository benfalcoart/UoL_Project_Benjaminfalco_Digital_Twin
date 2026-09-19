from pathlib import Path
import shutil
from API.camera_manager import CameraManager


manager = CameraManager()

output_directory = Path.home() / "beholder_test" / "camera_activation_test"

if output_directory.exists():
    shutil.rmtree(output_directory)

print("--- Initial State ---")
print(f"Detected cameras: {len(manager.cameras)}")
print(f"Active cameras:   {manager.get_number_active_cameras()}")

for camera in manager.cameras:
    print(f"{camera.name}: active={camera.active}")

if len(manager.cameras) < 3:
    raise RuntimeError("Test requires at least 3 cameras.")

print("\n--- Disabling Camera 3 ---")

success = manager.disable_camera(3)

print(f"Disable successful: {success}")
print(f"Detected cameras:   {len(manager.cameras)}")
print(f"Active cameras:     {manager.get_number_active_cameras()}")

assert success
assert manager.cameras[2].active is False
assert manager.get_number_active_cameras() == len(manager.cameras) - 1

print("\n--- Capture Test ---")

results = manager.capture_all(output_directory)

for result in sorted(results, key=lambda result: result.camera.id):
    print(
        f"{result.camera.name}: "
        f"success={result.success}, "
        f"path={result.output_path}"
    )

captured_ids = {
    result.camera.id
    for result in results
    if result.success
}

assert 3 not in captured_ids
assert len(results) == manager.get_number_active_cameras()

camera_3_path = output_directory / "cam_03.jpg"
assert not camera_3_path.exists()

print("\nCamera 3 was successfully excluded from capture.")

print("\n--- Re-enabling Camera 3 ---")

success = manager.enable_camera(3)

print(f"Enable successful: {success}")
print(f"Active cameras:    {manager.get_number_active_cameras()}")

assert success
assert manager.cameras[2].active is True
assert manager.get_number_active_cameras() == len(manager.cameras)

print("\nPASS: Camera activation controls behaved as expected.")