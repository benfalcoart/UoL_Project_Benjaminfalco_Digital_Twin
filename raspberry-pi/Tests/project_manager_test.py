from pathlib import Path
import shutil

from API.project_manager import ProjectManager


TEST_ROOT = Path.home() / "beholder_test" / "project_manager_test"


def reset_test_directory():
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)

    TEST_ROOT.mkdir(parents=True)


def main():
    reset_test_directory()

    print("--- Creating Project Manager ---")
    manager = ProjectManager(TEST_ROOT)

    print("\n--- Creating Project ---")
    project = manager.create_project("Morningstar Mill")

    print(f"Name:          {project.name}")
    print(f"Directory:     {project.directory}")
    print(f"Capture count: {project.capture_count}")
    print(f"Created:       {project.created}")

    assert project.name == "Morningstar Mill"
    assert project.directory.exists()
    assert (project.directory / "images").exists()
    assert (project.directory / "project.json").exists()
    assert manager.project_exists("Morningstar Mill")

    print("PASS: Project created successfully.")

    print("\n--- Testing Capture Counter ---")

    assert manager.get_next_capture_id() == 1
    assert manager.get_next_capture_id() == 2
    assert manager.get_next_capture_id() == 3

    assert manager.get_current_project().capture_count == 3

    print("PASS: Capture counter incremented to 3.")

    print("\n--- Simulating BEHOLDER Reboot ---")

    manager = ProjectManager(TEST_ROOT)

    assert manager.get_current_project() is None

    project = manager.open_project("Morningstar Mill")

    assert project.capture_count == 3
    assert project.name == "Morningstar Mill"

    print(f"Restored capture count: {project.capture_count}")
    print("PASS: Project metadata survived restart.")

    print("\n--- Simulating Interrupted Capture ---")

    images_directory = project.directory / "images"

    (images_directory / "000004_M1.jpg").write_bytes(b"test")
    (images_directory / "000004_M3.jpg").write_bytes(b"test")
    (images_directory / "000004_U2.jpg").write_bytes(b"test")

    print(f"Metadata capture count before refresh: {project.capture_count}")

    project = manager.refresh_current_project()

    print(f"Metadata capture count after refresh:  {project.capture_count}")

    assert project.capture_count == 4

    print("PASS: Filesystem recovery detected capture 4.")

    print("\n--- Testing Next Capture After Recovery ---")

    capture_id = manager.get_next_capture_id()

    assert capture_id == 5

    print(f"Next capture ID: {capture_id}")
    print("PASS: Capture numbering continued correctly.")

    print("\n--- Testing Project Statistics ---")

    image_count = manager.get_project_image_count("Morningstar Mill")
    project_size = manager.get_project_size("Morningstar Mill")

    print(f"Images: {image_count}")
    print(f"Size:   {project_size} bytes")

    assert image_count == 3
    assert project_size > 0

    print("PASS: Project statistics calculated.")

    print("\n--- Testing Project Listing ---")

    projects = manager.get_projects()

    assert len(projects) == 1
    assert projects[0].name == "Morningstar Mill"
    assert projects[0].capture_count == 5

    print("PASS: Existing projects discovered.")

    print("\n--- Testing Project Deletion ---")

    deleted = manager.delete_project("Morningstar Mill")

    assert deleted
    assert not manager.project_exists("Morningstar Mill")
    assert manager.get_current_project() is None

    print("PASS: Project deleted.")

    print("\n================================")
    print("ALL PROJECT MANAGER TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()