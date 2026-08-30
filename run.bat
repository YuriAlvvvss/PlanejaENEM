@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_DIR=%CD%"

if exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
) else if exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
) else (
    echo [INFO] Virtual environment not found. Creating one...
    python -m venv venv
    if exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
        set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
    ) else (
        echo [ERROR] Could not create Python virtual environment.
        exit /b 1
    )
)

if not exist "%PROJECT_DIR%\requirements.txt" (
    echo [ERROR] requirements.txt not found in project root.
    exit /b 1
)

"%PYTHON_EXE%" -m pip install --quiet -r "%PROJECT_DIR%\requirements.txt"

set "FLASK_ENV=development"
set "FLASK_DEBUG=1"
set "PORT=5000"
set "URL=http://localhost:%PORT%"

echo [INFO] Starting PlanejaENEM on %URL%
start "PlanejaENEM" "%PYTHON_EXE%" -c "import os; from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=os.environ.get('FLASK_DEBUG', '0').lower() in {'1', 'true', 'yes', 'on'}, use_reloader=False)"
start "" "%URL%"

endlocal
