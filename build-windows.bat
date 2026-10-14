@echo off
rem AkhavanLink - Created by Alireza Akhavan
rem Builds the portable Windows package on YOUR PC (needs Python 3.9+ from python.org).
rem The same thing is done automatically by GitHub Actions (see .github\workflows\build-client.yml).
setlocal
cd /d "%~dp0"
set /p SERVER=Server address (for example my-app.deplexo.app - or just press Enter to set it later in the app): 
py -3 -m pip install --upgrade pip pyinstaller
py -3 scripts\make_portable.py --server "%SERVER%"
echo.
echo Result: dist\AkhavanLink-Portable-Windows.zip
pause
