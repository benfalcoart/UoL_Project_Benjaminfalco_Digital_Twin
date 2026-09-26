from pydantic import BaseModel
from API.capture_controller import CaptureMode
#Request Models:
class CreateProjectRequest(BaseModel):
    name: str

class CaptureModeRequest(BaseModel):
    mode: CaptureMode

class CaptureIntervalRequest(BaseModel):
    seconds: float

class ProjectRequest(BaseModel):
    projectName: str


class CameraRequest(BaseModel):
    cameraId: int


class CameraSlotRequest(BaseModel):
    cameraId: int
    slot: str

class TransferFileRequest(BaseModel):
    projectName: str
    path: str

class CameraSettingUpdateRequest(BaseModel):
    setting: str
    value: int

class CameraSettingUpdateRequest(BaseModel):
    setting: str
    value: int


class CameraProfileRequest(BaseModel):
    profileName: str


class CameraProfileSaveRequest(BaseModel):
    name: str
    description: str = ""