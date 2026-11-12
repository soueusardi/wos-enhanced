@echo off
rem Builds "dist\Web of Shadows Launcher.exe" (a single file that opens the launcher).
rem Requires Python (the same one used by run_from_source.bat).
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean "Web of Shadows Launcher.spec"
if errorlevel 1 (
  echo.
  echo Build failed. See the messages above.
  pause
  exit /b 1
)
echo.
echo Done: "dist\Web of Shadows Launcher.exe"
echo User data (config, cache, skins, log) is stored in %%LOCALAPPDATA%%\Web of Shadows Launcher.
pause
