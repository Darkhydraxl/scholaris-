@echo off
title Scholaris — Dev Server
cd /d "%~dp0"

:loop
echo.
echo  ================================================
echo   Scholaris server starting on http://127.0.0.1:5000
echo   Close this window to stop the server.
echo  ================================================
echo.
python run.py
echo.
echo  [Server stopped — restarting in 3 seconds...]
timeout /t 3 /nobreak >nul
goto loop
