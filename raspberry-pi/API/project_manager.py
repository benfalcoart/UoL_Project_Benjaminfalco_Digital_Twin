from dataclasses import dataclass
from pathlib import Path
import shutil
import json
from datetime import datetime

"""
Data Class that represents each "project". Each location/model to be scanned will be considered a project
"""
@dataclass
class Project:
    name: str
    directory: Path
    capture_count: int = 0
    created: str = ""

"""
Project Management of the system. IO and Folder CRUD operations.
"""
class ProjectManager:
    def __init__(self, root_directory: Path):
        self.root_directory = root_directory
        self.current_project: Project | None = None
        self.root_directory.mkdir(parents=True, exist_ok=True)

    """
    Creates a new project folder directory. Checks for existing ones first.
    """
    def create_project(self, name: str) -> Project:
        if self.project_exists(name):
            raise ValueError(f"Project '{name}' already exists.")

        directory_name = self.sanitize_project_name(name)
        project_directory = self.root_directory / directory_name

        images_directory = project_directory / "images"
        images_directory.mkdir(parents=True)

        project = Project(name=name, directory=project_directory, capture_count=0, created=datetime.now().isoformat())
        self.save_project(project)

        self.current_project = project
        return project

    """
    Returns a specific Project
    """
    def get_project(self, name: str) -> Project:
        project_directory = self.get_project_directory(name)
        project = self.load_project(project_directory)
        return self.refresh_project(project)

    """
    Returns list of all Projects
    """
    def get_projects(self) -> list[Project]:
        projects = []

        for directory in self.root_directory.iterdir():
            if directory.is_dir():
                try:
                    projects.append(self.load_project(directory))
                except FileNotFoundError:
                    continue

        return projects

    """
    'Refreshes' the Project, by getting the highest ID. this is used when opening a project. 
    If a power outage causes a system failure this is a better way to recover the project status
    Searches for the highest ID image to restart the counter.
    """
    def refresh_project(self, project: Project) -> Project:
        images_directory = project.directory / "images"

        if not images_directory.exists():
            images_directory.mkdir(parents=True)

        highest_capture_id = 0

        for file in images_directory.iterdir():
            if not file.is_file():
                continue

            if file.suffix.lower() not in {".jpg", ".jpeg"}:
                continue

            parts = file.stem.split("_")

            if not parts:
                continue

            try:
                capture_id = int(parts[0])
            except ValueError:
                continue

            highest_capture_id = max(
                highest_capture_id,
                capture_id
            )

        if highest_capture_id > project.capture_count:
            project.capture_count = highest_capture_id
            self.save_project(project)

        return project

    """
    Refreshes the current project.
    """
    def refresh_current_project(self) -> Project | None:
        if self.current_project is None:
            return None

        return self.refresh_project(self.current_project)

    """
    Opens a Project Directory and loads it into the system for use.
    """
    def open_project(self, name: str) -> Project:
        project_directory = self.get_project_directory(name)

        project = self.load_project(project_directory)
        project = self.refresh_project(project)

        self.current_project = project
        return project

    """
    Deletes a project Directory (This is dangerous and cannot be undone!)
    """
    def delete_project(self, name: str) -> bool:
        if not self.project_exists(name):
            return False

        project_directory = self.get_project_directory(name)

        shutil.rmtree(project_directory)

        if self.current_project is not None and self.current_project.directory == project_directory:
            self.current_project = None

        return True

    """
    Closes Current Project
    """
    def close_project(self) -> None:
        self.current_project = None
    """
    Saves Project Metadata for reload later.
    """
    def save_project(self, project: Project) -> None:
        if not project.directory.is_dir():
            raise FileNotFoundError(f"Project directory does not exist: {project.directory}")

        metadata_path = project.directory / "project.json"

        metadata = {
            "name": project.name,
            "captureCount": project.capture_count,
            "created": project.created
        }

        metadata_path.write_text(json.dumps(metadata, indent=4))

    """
    Loads Project Metadata
    """
    def load_project(self, project_directory: Path) -> Project:
        metadata_path = project_directory / "project.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Project metadata does not exist: {metadata_path}")

        metadata = json.loads(metadata_path.read_text())
        return Project(name=metadata["name"], directory=project_directory, capture_count=metadata["captureCount"], created=metadata["created"])

    """
    returns the current Project. If not set returns None.
    """
    def get_current_project(self) -> Project | None:
        return self.current_project

    """
    Santizes Project name for better file system management. This is not a full santization but should be fine for english input.
    """
    def sanitize_project_name(self, name: str) -> str:
        #allow for spaces but replace them with underscores.
        sanitized = name.strip().replace(" ", "_")

        allowed_characters = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789_-"
        )

        sanitized = "".join(character for character in sanitized if character in allowed_characters)

        if not sanitized:
            raise ValueError("Project name must contain valid characters.")

        return sanitized

    """
    Checks if the project exists
    """
    def project_exists(self, name: str) -> bool:
        directory_name = self.sanitize_project_name(name)
        return (self.root_directory / directory_name).is_dir()

    """
    gets the project directory by name
    """
    def get_project_directory(self, name: str) -> Path:
        directory_name = self.sanitize_project_name(name)
        project_directory = self.root_directory / directory_name

        if not project_directory.is_dir():
            raise FileNotFoundError(f"Project '{name}' does not exist.")

        return project_directory

    """
    Gets the current Project's Directory/location
    """
    def get_current_project_directory(self) -> Path | None:
        if self.current_project is None:
            return None

        return self.current_project.directory

    """
    Gets the current project's Size
    """
    def get_project_size(self, name: str) -> int:
        project_directory = self.get_project_directory(name)

        total_size = 0

        for file in project_directory.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size

        return total_size

    """
    Gets the number of images the project contains.
    """
    def get_project_image_count(self, name: str) -> int:
        project_directory = self.get_project_directory(name)
        images_directory = project_directory / "images"

        if not images_directory.exists():
            return 0

        return sum(1 for file in images_directory.iterdir() if file.is_file() and file.suffix.lower() in {".jpg", ".jpeg"})

    """
    gets next incremented capture id
    """
    def get_next_capture_id(self) -> int:
        if self.current_project is None:
            raise RuntimeError("No project is currently open.")

        self.current_project.capture_count += 1
        self.save_project(self.current_project)

        return self.current_project.capture_count