from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from datetime import datetime
import asyncio
from API.system_monitor import (
    get_cpu_temperature,
    get_storage_free_gb,
    get_timestamp,
    get_active_camera_count,
    get_battery_percentage
)

#set up the beholder API 
app = FastAPI(title="BEHOLDER API", version="0.1.0")

connected_clients: list[WebSocket] = []


class CaptureRequest(BaseModel):
    session_name: str = "default"

#Returns the current status of the Raspberry Pi and connected hardware.
#TODO: Some hardware monitoring functions are still stubs and need to be implemented on the Pi.
@app.get("/api/status")
@app.get("/api/status")
async def get_status():
    return {
        "state": "READY",
        "battery": get_battery_percentage(),
        "temperature": get_cpu_temperature(),
        "storageFreeGb": get_storage_free_gb(),
        "cameraCount": get_active_camera_count(),
        "timestamp": get_timestamp()
    }

#Starts an asynchronous capture operation.
#TODO: Capture is currently simulated and needs to be integrated with the camera hardware.
@app.post("/api/capture")
@app.post("/api/capture")
async def capture(request: CaptureRequest):
    asyncio.create_task(run_capture(request.session_name))

    return {
        "accepted": True,
        "sessionName": request.session_name
    }

#TODO: Stub. Needs to be fleshed out with actual hardware.
async def run_capture(session_name: str):
    await broadcast({
        "type": "capture_started",
        "sessionName": session_name
    })

    await asyncio.sleep(2)

    for camera_id in range(1, 5):
        await broadcast({
            "type": "camera_capture_complete",
            "cameraId": camera_id,
            "sessionName": session_name
        })

        await asyncio.sleep(0.5)

    await broadcast({
        "type": "capture_complete",
        "sessionName": session_name,
        "successfulCameras": 4,
        "failedCameras": 0
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