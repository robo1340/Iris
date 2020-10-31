REM A batch script to execute a Python script
echo %0\..

set "newDir=%~dp0%..\"
echo %newDir%

"%newDir%WinPython\python-3.5.4.amd64\python.exe" main.py config.ini

EXIT