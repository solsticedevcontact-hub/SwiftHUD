@echo off
echo === Building SwiftHUD.exe ===
python -m pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --uac-admin ^
  --name SwiftHUD --version-file version_info.txt ^
  --collect-all customtkinter --collect-all GPUtil --collect-all keyboard ^
  swifthud.py
echo.
echo Done: dist\SwiftHUD.exe
echo Next: run sign_exe.ps1 (PowerShell as Administrator) to sign it.
pause
