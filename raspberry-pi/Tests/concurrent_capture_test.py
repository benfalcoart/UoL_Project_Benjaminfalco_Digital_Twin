"""
Testing concurrent/multithreaded camera capture.
"""

from pathlib import Path
from API.camera_manager import CameraManager

manager = CameraManager()

output_directory = (Path.home() / "beholder_test" / "concurrent_capture_test")
print(f"Detected cameras: {len(manager.cameras)}")

for camera in manager.cameras:
    print(f"{camera.name}: {camera.device}")

results = manager.capture_all(output_directory)

print()

for result in sorted(results, key=lambda r: r.camera.id):
    print(
        f"{result.camera.name}: "
        f"success={result.success}, "
        f"attempts={len(result.attempts)}, "
        f"output={result.output_path}"
    )

    for attempt in result.attempts:
        if not attempt.success:
            print(f"Attempt {attempt.attempt} failed: {attempt.error}")

successful = sum(result.success for result in results)
failed = len(results) - successful

print()
print(f"Successful cameras: {successful}")
print(f"Failed cameras: {failed}")