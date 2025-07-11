@echo off
SET PY_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python313
SET SCRIPT_PATH=C:\counting\main.py
SET LOG_PATH=C:\counting\start_app.log

echo [%date% %time%] Starting app... >> "%LOG_PATH%"
start "" "%PY_PATH%\pythonw.exe" "%SCRIPT_PATH%"
echo [%date% %time%] App started silently. >> "%LOG_PATH%"
echo App started successfully. Closing in 5 seconds...
timeout /t 5 >nul
exit