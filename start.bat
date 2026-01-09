@echo off
echo ============================================
echo Starting Lead Generation Pipeline
echo ============================================
echo.

echo Starting API Backend (Port 8000)...
start "API Backend" cmd /k "venv\Scripts\activate.bat && python backend\api.py"

timeout /t 2 /nobreak >nul

echo Starting Frontend (Port 3000)...
start "Frontend" cmd /k "npm run dev"

echo.
echo ============================================
echo All services started!
echo ============================================
echo.
echo Access the application at:
echo - Frontend Dashboard: http://localhost:3000
echo - API Backend: http://localhost:8000
echo - API Docs: http://localhost:8000/docs
echo - n8n Editor: http://localhost:5678
echo.
echo Press any key to stop all services...
pause >nul

echo Stopping services...
taskkill /FI "WindowTitle eq API Backend*" /T /F
taskkill /FI "WindowTitle eq Frontend*" /T /F
