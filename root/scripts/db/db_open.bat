@echo off
setlocal ENABLEEXTENSIONS
set "SCRIPT_DIR=%~dp0"
cd /D "%SCRIPT_DIR%\..\.."
set "DB=%CD%\data\db\api_index.db"
sqlite3 "%DB%"
pause
