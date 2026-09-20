from datetime import datetime
import threading
import time

from API.app_state import (
    camera_manager,
    project_manager,
    capture_controller,
    clicker
)
from API.capture_controller import CaptureMode


def wait_until(condition, timeout: float) -> bool:
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if condition():
            return True

        time.sleep(0.1)

    return False


def get_capture_images(images_directory, capture_id: int):
    prefix = f"{capture_id:06d}_"
    return sorted(
        file
        for file in images_directory.glob("*.jpg")
        if file.name.startswith(prefix)
    )


def main():
    print("--- BEHOLDER Capture System Test ---")

    detected = len(camera_manager.cameras)
    active = camera_manager.get_number_active_cameras()

    print(f"Detected cameras: {detected}")
    print(f"Active cameras:   {active}")

    assert active > 0, "No active cameras detected."

    project_name = (
        "BEHOLDER_System_Test_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    project = project_manager.create_project(project_name)
    images_directory = project.directory / "images"

    print(f"Test project: {project.name}")
    print(f"Images:       {images_directory}")

    clicker_thread = threading.Thread(
        target=clicker.listen,
        daemon=True
    )
    clicker_thread.start()

    print("\n--- SINGLE SHOT TEST ---")

    capture_controller.set_mode(CaptureMode.SINGLE)

    starting_count = project.capture_count

    print("Press Page Up or Page Down ONCE on the clicker...")

    triggered = wait_until(
        lambda: project.capture_count > starting_count,
        30
    )

    assert triggered, "Timed out waiting for clicker trigger."

    capture_id = project.capture_count

    finished = wait_until(
        lambda: not capture_controller.capturing,
        30
    )

    assert finished, "Single capture did not finish."

    images = get_capture_images(
        images_directory,
        capture_id
    )

    print(f"Capture ID: {capture_id}")
    print(f"Images:     {len(images)}")

    for image in images:
        print(f"  {image.name}")

    assert len(images) == active, (
        f"Expected {active} images, found {len(images)}."
    )

    print("PASS: Single-shot clicker capture.")

    print("\n--- AUTOMATIC MODE TEST ---")

    capture_controller.set_mode(CaptureMode.AUTOMATIC)

    starting_count = project.capture_count

    print("Press the clicker ONCE to START rapid fire...")

    started = wait_until(
        lambda: capture_controller.automatic_running,
        30
    )

    assert started, "Timed out waiting for automatic mode to start."

    print("Automatic capture started.")
    print("Waiting for at least 3 capture events...")

    captured_three = wait_until(
        lambda: project.capture_count >= starting_count + 3,
        30
    )

    assert captured_three, "Automatic mode did not produce 3 captures."

    print("Press the clicker AGAIN to STOP rapid fire...")

    stopped = wait_until(
        lambda: not capture_controller.automatic_running,
        30
    )

    assert stopped, "Timed out waiting for automatic mode to stop."

    finished = wait_until(
        lambda: not capture_controller.capturing,
        30
    )

    assert finished, "Final automatic capture did not finish."

    ending_count = project.capture_count

    print(f"Automatic captures: {ending_count - starting_count}")

    print("\n--- CAPTURE SUMMARY ---")

    for capture_id in range(1, ending_count + 1):
        images = get_capture_images(
            images_directory,
            capture_id
        )

        print(
            f"Capture {capture_id:06d}: "
            f"{len(images)}/{active} images"
        )

    print("\n================================")
    print("BEHOLDER CAPTURE SYSTEM PASSED")
    print("================================")
    print(f"Test data retained at:")
    print(project.directory)


if __name__ == "__main__":
    main()