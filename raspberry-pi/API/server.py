import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from API.capture_controller import CaptureMode
from API.app_state import (
    camera_manager,
    project_manager,
    capture_controller,
    clicker
)
from API.system_monitor import (
    get_cpu_temperature,
    get_storage_free_gb,
    get_timestamp,
    get_detected_camera_count,
    get_active_camera_count,
    get_battery_status
)
import threading
from contextlib import asynccontextmanager

api_version = "1.0.0"

class CreateProjectRequest(BaseModel):
    name: str

#set up listener for the clicker to take photos
@asynccontextmanager
async def lifespan(app: FastAPI):
    clicker_thread = threading.Thread(target=clicker.listen, daemon=True)
    clicker_thread.start()

    status_task = asyncio.create_task(status_broadcast_loop())
    yield

    status_task.cancel()
    

#set up the beholder API 
app = FastAPI(title="BEHOLDER API", version=api_version, lifespan=lifespan)

connected_clients: list[WebSocket] = []

class CaptureModeRequest(BaseModel):
    mode: CaptureMode

class CaptureIntervalRequest(BaseModel):
    seconds: float

#Returns the current status of the Raspberry Pi and connected hardware.
@app.get("/api/status")
async def get_status():
    return build_status_snapshot()

@app.post("/api/projects")
async def create_project(request: CreateProjectRequest):
    try:
        project = project_manager.create_project(request.name)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return {
        "name": project.name,
        "directory": str(project.directory),
        "captureCount": project.capture_count
    }

@app.get("/api/cameras")
async def get_cameras():
    return [
        {
            "id": camera.id,
            "device": camera.device,
            "name": camera.name,
            "active": camera.active,
            "slot": camera.slot.value
        }
        for camera in camera_manager.cameras
    ]

@app.put("/api/capture/mode")
async def set_capture_mode(request: CaptureModeRequest):
    capture_controller.set_mode(request.mode)

    return {
        "mode": capture_controller.mode.value
    }

@app.post("/api/cameras/{camera_id}/enable")
async def enable_camera(camera_id: int):
    success = camera_manager.enable_camera(camera_id)

    return {
        "success": success,
        "cameraId": camera_id,
        "active": True if success else None
    }


@app.post("/api/cameras/{camera_id}/disable")
async def disable_camera(camera_id: int):
    success = camera_manager.disable_camera(camera_id)

    return {
        "success": success,
        "cameraId": camera_id,
        "active": False if success else None
    }

@app.put("/api/capture/interval")
async def set_capture_interval(request: CaptureIntervalRequest):
    capture_controller.set_automatic_interval(request.seconds)

    return {
        "interval": capture_controller.automatic_interval
    }

@app.get("/api/capture/status")
async def get_capture_status():
    return {
        "mode": capture_controller.mode.value,
        "capturing": capture_controller.capturing,
        "automaticRunning": capture_controller.automatic_running,
        "automaticInterval": capture_controller.automatic_interval
    }

@app.post("/api/capture/trigger")
async def trigger_capture():
    capture_controller.trigger()

    return {
        "accepted": True,
        "mode": capture_controller.mode.value,
        "automaticRunning": capture_controller.automatic_running
    }

@app.get("/api/projects")
async def get_projects():
    return [
        {
            "name": project.name,
            "captureCount": project.capture_count,
            "created": project.created
        }
        for project in project_manager.get_projects()
    ]

@app.post("/api/projects/{project_name}/open")
async def open_project(project_name: str):
    project = project_manager.open_project(project_name)

    return {
        "name": project.name,
        "captureCount": project.capture_count,
        "created": project.created
    }

@app.get("/api/projects/current")
async def get_current_project():
    project = project_manager.get_current_project()

    if project is None:
        return None

    return {
        "name": project.name,
        "captureCount": project.capture_count,
        "created": project.created
    }

def build_status_snapshot():
    battery = get_battery_status()
    project = project_manager.get_current_project()

    return {
        "timestamp": get_timestamp(),

        "system": {
            "state": "READY",
            "temperatureC": get_cpu_temperature(),
            "storageFreeGb": get_storage_free_gb(),
            "battery": None if battery is None else {
                "percentage": battery.percentage,
                "voltage": battery.voltage,
                "currentA": battery.current,
                "powerW": battery.power
            }
        },

        "project": None if project is None else {
            "name": project.name,
            "lastCaptureId": project.capture_count
        },

        "capture": {
            "mode": capture_controller.mode.value,
            "capturing": capture_controller.capturing,
            "automaticRunning": capture_controller.automatic_running,
            "automaticIntervalSeconds": capture_controller.automatic_interval
        },

        "cameras": {
            "detectedCount": len(camera_manager.cameras),
            "activeCount": camera_manager.get_number_active_cameras(),
            "items": [
                {
                    "id": camera.id,
                    "name": camera.name,
                    "active": camera.active,
                    "slot": camera.slot.value
                }
                for camera in camera_manager.cameras
            ]
        }
    }

#websocket broadcast function for sending data to clients.
async def broadcast(message: dict):
    disconnected_clients = []

    for websocket in connected_clients:
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected_clients.append(websocket)

    for websocket in disconnected_clients:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def status_broadcast_loop():
    while True:
        await broadcast({
            "type": "status_update",
            **build_status_snapshot()
        })

        await asyncio.sleep(1.0)

#connect to the websocket/setup connection.
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        await websocket.send_json({
            "type": "connected",
            "apiVersion": api_version,
            "timestamp": get_timestamp()
        })

        await websocket.send_json({
            "type": "status_update",
            **build_status_snapshot()
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)