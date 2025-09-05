@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /D "%SCRIPT_DIR%\..\.."
set "DB=%CD%\data\db\api_index.db"
set "SCHEMA=%CD%\src\codetutor\adapters\python\scan\schema.sql"
if not exist "%DB%" ( mkdir "%CD%\data\db" >nul 2>&1 )
sqlite3 "%DB%" ".read %SCHEMA%"
echo Initialized %DB% with %SCHEMA%
pause
