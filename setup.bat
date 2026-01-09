@echo off
echo ============================================
echo Lead Generation Pipeline - Setup
echo ============================================
echo.

echo Creating virtual environment...
python -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Creating data directory...
if not exist "data" mkdir data

echo.
echo Initializing database...
python backend\database.py

echo.
echo Installing Node.js dependencies...
call npm install

echo.
echo ============================================
echo Setup complete!
echo ============================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env and configure your settings
echo 2. Add your GROQ_API_KEY to .env
echo 3. Run 'start.bat' to launch all services
echo.
pause
