import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

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
    get_battery_status
)
import API.models.server_request_models as request_models
import threading
from contextlib import asynccontextmanager

api_version = "1.0.0"

#set up listener for the clicker to take photos
@asynccontextmanager
async def lifespan(app: FastAPI):
    clicker_thread = threading.Thread(target=clicker.listen, daemon=True)
    clicker_thread.start()
    status_task = asyncio.create_task(status_broadcast_loop())

    try:
        yield

    finally:
        status_task.cancel()
    

#set up the beholder API 
app = FastAPI(title="BEHOLDER API", version=api_version, lifespan=lifespan)

connected_clients: list[WebSocket] = []

#Returns the current status of the Raspberry Pi and connected hardware.
@app.get("/api/status")
async def get_status():
    return build_status_snapshot()

@app.post("/api/projects")
async def create_project(request: request_models.CreateProjectRequest):
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
async def set_capture_mode(request: request_models.CaptureModeRequest):
    capture_controller.set_mode(request.mode)

    return {
        "mode": capture_controller.mode.value
    }

@app.post("/api/cameras/enable")
async def enable_camera(request: request_models.CameraRequest):
    try:
        success = camera_manager.enable_camera(request.cameraId)

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not success:
        raise HTTPException(status_code=404, detail=f"Camera {request.cameraId} does not exist.")

    return {
        "success": True,
        "cameraId": request.cameraId,
        "active": True
    }


@app.post("/api/cameras/disable")
async def disable_camera(request: request_models.CameraRequest):
    try:
        success = camera_manager.disable_camera(request.cameraId)

    except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    if not success:
        raise HTTPException(status_code=404, detail=f"Camera {request.cameraId} does not exist.")

    return {
        "success": True,
        "cameraId": request.cameraId,
        "active": False
    }

@app.put("/api/cameras/slot")
async def set_camera_slot(request: request_models.CameraSlotRequest):
    success = camera_manager.set_camera_slot(request.cameraId, request.slot)

    if not success:
        raise HTTPException(status_code=400, detail="Unable to assign camera slot.")

    return {
        "success": True,
        "cameraId": request.cameraId,
        "slot": request.slot
    }

@app.post("/api/cameras/identify")
async def identify_camera(request: request_models.CameraRequest):
    if capture_controller.capturing:
        raise HTTPException(
            status_code=409,
            detail="A capture is currently in progress."
        )

    if capture_controller.automatic_running:
        raise HTTPException(
            status_code=409,
            detail="Automatic capture is currently running."
        )

    result = camera_manager.identify_camera(
        request.cameraId
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Camera {request.cameraId} does not exist."
        )

    if not result.success:
        error = (result.attempts[-1].error if result.attempts else "Unknown capture error.")

        raise HTTPException(status_code=500, detail=error)

    return FileResponse(path=result.output_path, media_type="image/jpeg", filename=f"camera_{request.cameraId}_identify.jpg", background=BackgroundTask(result.output_path.unlink, missing_ok=True))

@app.put("/api/capture/interval")
async def set_capture_interval(request: request_models.CaptureIntervalRequest):
    try:
        capture_controller.set_automatic_interval(request.seconds)

        return {
            "interval": capture_controller.automatic_interval
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

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
            "created": project.created,
            "imageCount": project_manager.get_project_image_count(
                project.name
            ),
            "sizeBytes": project_manager.get_project_size(
                project.name
            )
        }
        for project in project_manager.get_projects()
    ]

@app.post("/api/projects/open")
async def open_project(request: request_models.ProjectRequest):
    try:
        project = project_manager.open_project(request.projectName)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    return {
        "name": project.name,
        "captureCount": project.capture_count,
        "created": project.created
    }

@app.post("/api/projects/close")
async def close_project():
    if capture_controller.automatic_running:
        capture_controller.stop_automatic()

    project_manager.close_project()

    return {
        "success": True
    }

@app.post("/api/projects/delete")
async def delete_project(request: request_models.ProjectRequest):
    success = project_manager.delete_project(request.projectName)

    if not success:
        raise HTTPException(status_code=404, detail=f"Project '{request.projectName}' does not exist.")

    return {
        "success": True,
        "projectName": request.projectName
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

@app.post("/api/projects/transfer/manifest")
async def get_transfer_manifest(request: request_models.ProjectRequest):
    try:
        project = project_manager.get_project(request.projectName)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    files = []
    total_bytes = 0

    for file_path in project.directory.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(project.directory)
        size = file_path.stat().st_size

        files.append({
            "path": relative_path.as_posix(),
            "sizeBytes": size
        })

        total_bytes += size

    return {
        "projectName": project.name,
        "fileCount": len(files),
        "totalBytes": total_bytes,
        "files": files
    }

@app.post("/api/projects/transfer/file")
async def transfer_project_file(request: request_models.TransferFileRequest):
    try:
        project = project_manager.get_project(request.projectName)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    project_root = project.directory.resolve()
    requested_file = (project_root / request.path).resolve()

    try:
        requested_file.relative_to(project_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid project file path.")

    if not requested_file.is_file():
        raise HTTPException(status_code=404, detail="Project file does not exist.")

    return FileResponse(path=requested_file)

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
        try:
            await broadcast({
                "type": "status_update",
                **build_status_snapshot()
            })

        except asyncio.CancelledError:
            raise

        except Exception as error:
            print(f"Status broadcast error: {error}")

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