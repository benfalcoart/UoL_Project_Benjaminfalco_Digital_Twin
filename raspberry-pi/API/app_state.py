"""
This script will control the whole app and all of the systems will be routed through here.
"""
from pathlib import Path

from API.camera_manager import CameraManager
from API.project_manager import ProjectManager
from API.capture_controller import CaptureController
from API.clicker import Clicker


camera_manager = CameraManager()
project_manager = ProjectManager(Path.home() / "beholder_captures")
capture_controller = CaptureController(camera_manager, project_manager)
clicker = Clicker(capture_controller)