@echo off
rem Runs the launcher from source (for development). End users should use "Web of Shadows Launcher.exe" from Releases.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python launcher.py
