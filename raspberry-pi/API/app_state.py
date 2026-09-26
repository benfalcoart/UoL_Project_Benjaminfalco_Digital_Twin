"""
This script will control the whole app and all of the systems will be routed through here.
"""
from pathlib import Path

from API.camera_manager import CameraManager
from API.camera_profile_manager import CameraProfileManager
from API.project_manager import ProjectManager
from API.capture_controller import CaptureController
from API.clicker import Clicker


camera_manager = CameraManager()
#Path the Camera Settings:
profile_directory = Path(__file__).resolve().parents[1] / "config" / "camera_profiles"
camera_profile_manager = CameraProfileManager(camera_manager, Path(__file__).resolve().parents[1] / "config" / "camera_profiles")

project_manager = ProjectManager(Path.home() / "beholder_captures")
capture_controller = CaptureController(camera_manager, project_manager)
clicker = Clicker(capture_controller)