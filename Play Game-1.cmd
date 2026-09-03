@echo off
setlocal
rem Game-1 - double-click to build the C# and PLAY the Godot (3D) build.
rem   Pass-through args work too, e.g.:  "Play Game-1.cmd" --editor
rem The game runs IN THIS TERMINAL and streams all output, so any crash stays on
rem screen. The window stays open after the game exits (pause below).
set "REPO=%~dp0"
set "PY=%REPO%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%REPO%launch.py" %*
echo.
echo ===== Game-1 exited (errorlevel %errorlevel%). Close this window when done. =====
pause
