@echo off
rem Double-click to remove the desktop calendar completely.
echo This will close the calendar and stop it starting with Windows.
choice /M "Continue"
if errorlevel 2 exit /b

rem 1) close the running calendar
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*calendar_desktop.pyw*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

rem 2) remove auto-start
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v DesktopCalendar /f >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DesktopCalendar.vbs" >nul 2>nul

rem 3) saved events (asks first)
choice /M "Also delete your saved events, colors and notes"
if errorlevel 2 goto files
del "%USERPROFILE%\desktop_calendar_data.json*" >nul 2>nul
del "%USERPROFILE%\desktop_calendar_data.json.tmp" >nul 2>nul
del "%USERPROFILE%\desktop_calendar_error.log" >nul 2>nul
del "%USERPROFILE%\desktop_calendar_notes.txt*" >nul 2>nul

:files
rem 4) remove the calendar's own files from this folder
cd /d "%~dp0"
del "calendar_desktop.pyw" "install_windows.bat" "install_mac.command" >nul 2>nul
echo Calendar removed. You can delete this folder now if it is empty.
pause
(goto) 2>nul & del "%~f0"
