@echo off
title Sleep Study Transfer Utility
cd /d "%~dp0"
if not exist "C:\Python27\python.exe" goto nope
"C:\Python27\python.exe" "%~dp0StudyTransfer_Final.py"
goto end
:nope
echo Python 2.7 not found at C:\Python27\python.exe
pause
:end
