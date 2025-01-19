@echo off
set "REQUIREMENTS=requirements.txt"
set "APP=app.py"

REM Step 1: Install dependencies
echo Installing dependencies from %REQUIREMENTS%...
pip install -r %REQUIREMENTS%

REM Step 2: Run the application
echo Running the application...
python %APP%
