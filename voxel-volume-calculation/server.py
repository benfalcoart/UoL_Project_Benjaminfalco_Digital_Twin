from pathlib import Path
from uuid import uuid4
import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from services.volume_calculator import VolumeCalculator


app = FastAPI()

#Since App testing environment has the viewer on a different origin, we need to allow it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

volumeCalculator = VolumeCalculator()


@app.post("/api/volume")
async def calculate_volume(
    mesh: UploadFile = File(...),
    boundaries: UploadFile = File(...)
):
    meshExtension = Path(mesh.filename).suffix.lower()

    if meshExtension != ".glb":
        raise HTTPException(
            status_code=400,
            detail="Expected mesh upload to be a GLB file"
        )

    meshPath = TEMP_DIR / f"{uuid4()}.glb"

    try:
        #Save the uploaded mesh:
        with meshPath.open("wb") as file:
            while chunk := await mesh.read(1024 * 1024):
                file.write(chunk)

        #Read the boundary JSON:
        boundaryBytes = await boundaries.read()
        boundaryData = json.loads(boundaryBytes)

        #Pass everything to the volume calculator:
        result = volumeCalculator.calculate(
            meshPath,
            boundaryData
        )

        return result

    finally:
        if meshPath.exists():
            meshPath.unlink()