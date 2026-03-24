@echo off
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Generating icon...
python generate_icon.py

echo.
echo Building standalone executable...
pyinstaller --onefile --windowed --noconsole --name DisplaySwitcher --icon=icon.ico ^
    --collect-all pystray ^
    --hidden-import six ^
    display_switcher.py

echo.
echo Clearing Windows icon cache (restarting Explorer)...
taskkill /F /IM explorer.exe >nul 2>&1
del /A /Q "%LocalAppData%\IconCache.db" >nul 2>&1
del /A /F /Q "%LocalAppData%\Microsoft\Windows\Explorer\iconcache_*.db" >nul 2>&1
start explorer.exe

echo.
echo Done! Executable is in the "dist" folder.
echo.
echo IMPORTANT: Unpin the old shortcut, then re-pin dist\DisplaySwitcher.exe
pause
