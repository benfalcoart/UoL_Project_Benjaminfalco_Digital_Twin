from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
from API.project_manager import ProjectManager

import asyncio
from API.system_monitor import (
    camera_manager,
    get_cpu_temperature,
    get_storage_free_gb,
    get_timestamp,
    get_detected_camera_count,
    get_active_camera_count,
    get_battery_status
)


class CreateProjectRequest(BaseModel):
    name: str

project_manager = ProjectManager(
    Path.home() / "beholder_captures"
)

#set up the beholder API 
app = FastAPI(title="BEHOLDER API", version="0.1.0")

connected_clients: list[WebSocket] = []


class CaptureRequest(BaseModel):
    session_name: str = "default"

#Returns the current status of the Raspberry Pi and connected hardware.
@app.get("/api/status")
async def get_status():
    battery = get_battery_status()

    return {
        "state": "READY",
        "battery": None if battery is None else {
            "percentage": battery.percentage,
            "voltage": battery.voltage,
            "current": battery.current,
            "power": battery.power
        },
        "temperature": get_cpu_temperature(),
        "storageFreeGb": get_storage_free_gb(),
        "detectedCameraCount": get_detected_camera_count(),
        "activeCameraCount": get_active_camera_count(),
        "timestamp": get_timestamp()
    }

@app.post("/api/projects")
async def create_project(request: CreateProjectRequest):
    project = project_manager.create_project(request.name)

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

#Starts an asynchronous capture operation.
@app.post("/api/capture")
async def capture():
    project = project_manager.get_current_project()

    if project is None:
        return {
            "accepted": False,
            "error": "No project selected."
        }

    asyncio.create_task(run_capture(project))

    return {
        "accepted": True,
        "project": project.name
    }

async def run_capture(project_name: str):
    await broadcast({
        "type": "capture_started",
        "sessionName": project_name
    })

    output_directory = (
        Path.home()
        / "beholder_captures"
        / project_name
    )

    results = await asyncio.to_thread(
        camera_manager.capture_all,
        output_directory
    )

    for result in results:
        await broadcast({
            "type": "camera_capture_complete",
            "cameraId": result.camera.id,
            "slot": result.camera.slot.value,
            "success": result.success,
            "sessionName": project_name
        })

    successful = sum(1 for result in results if result.success)
    failed = sum(1 for result in results if not result.success)

    await broadcast({
        "type": "capture_complete",
        "sessionName": project_name,
        "successfulCameras": successful,
        "failedCameras": failed
    })

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

#connect to the websocket/setup connection.
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    await websocket.send_json({
        "type": "connected",
        "state": "READY"
    })

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)