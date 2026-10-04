@echo off
setlocal

rem Project root is the folder containing this BAT file:
set "ROOT=%~dp0"
set "PYTHON=C:\Users\Ben\AppData\Local\Programs\Python\Python314\python.exe"

echo Starting Vite frontend...
start "Digital Twin - Frontend" cmd /k "cd /d ""%ROOT%viewer"" && npm run dev"

echo Starting Python voxel backend...
start "Digital Twin - Backend" cmd /k "cd /d ""%ROOT%voxel-volume-calculation"" && ""%PYTHON%"" -m uvicorn server:app --reload"

echo.
echo Both servers have been launched in separate windows.
endlocal
