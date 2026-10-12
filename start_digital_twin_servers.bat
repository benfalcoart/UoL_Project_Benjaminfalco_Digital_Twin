@echo off
setlocal

rem Project root is the folder containing this BAT file:
set "ROOT=%~dp0"
set "PYTHON=C:\Users\Ben\AppData\Local\Programs\Python\Python314\python.exe"

echo ========================================
echo         Digital Twin Loading
echo ========================================
echo.

rem Start Voxel API on port 8000:
echo Starting Python Voxel API...
start "Voxel API" cmd /k "cd /d ""%ROOT%voxel-volume-calculation"" && ""%PYTHON%"" -m uvicorn server:app --host 127.0.0.1 --port 8000 --log-level debug"

rem Start Machine Learning API on port 8001:
echo Starting Python ML API...
start "Machine Learning API" cmd /k "cd /d ""%ROOT%machine-learning"" && ""%PYTHON%"" -m uvicorn server:app --host 127.0.0.1 --port 8001 --log-level debug"

rem Start Three.js frontend:
echo Starting Vite frontend...
start "3D Viewer" cmd /k "cd /d ""%ROOT%viewer"" && npm run dev -- --host 127.0.0.1 --port 5173"
echo.
echo ========================================
echo All three services have been launched!
echo ========================================
echo.
echo 3D Viewer:    http://localhost:5173
echo Voxel API: http://localhost:8000/
echo Machine Learning API:    http://localhost:8001/
echo.
echo ML Reconstructions:
echo http://localhost:5173/api/ml/reconstructions
echo.
endlocal
