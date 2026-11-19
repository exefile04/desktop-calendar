@echo off
rem Double-click once. The calendar starts now, and adds itself to Windows startup.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw "calendar_desktop.pyw" & goto done)
where pythonw >nul 2>nul && (start "" pythonw "calendar_desktop.pyw" & goto done)
echo Python was not found. Install it from python.org (tick "Add Python to PATH"), then run this again.
pause
exit /b
:done
echo Done. The calendar is on your desktop and will start with Windows.
echo Keep this folder where it is.
timeout /t 6 >nul
