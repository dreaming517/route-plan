@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 goto start_server_py

where python >nul 2>&1
if %errorlevel%==0 goto start_server_python

echo 未检测到 Python，将直接打开网页。
start "" "%~dp0index.html"
pause
exit /b

:start_server_py
start "" "http://localhost:5173/"
py -m http.server 5173
exit /b

:start_server_python
start "" "http://localhost:5173/"
python -m http.server 5173
exit /b
