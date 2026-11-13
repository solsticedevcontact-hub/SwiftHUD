# SwiftHUD | سويفت هود
PC Swift & Gaming HUD for Windows, by **SoslticeDeveloper**.

## Features
- Specs & OS Advisor (CPU, GPU, RAM, SSD/HDD + recommended Windows)
- Deep Clean: Temp, Windows Temp, Prefetch, Chrome/Brave/Edge cache, Recycle Bin (skips locked files)
- RAM Booster (trims process working sets)
- Floating Mini-HUD (frameless, draggable, double-click = clean + boost, right-click = close)
- Move folders/games to another drive using Directory Junctions (with rollback on failure)
- Temperature (best effort, depends on hardware/BIOS support)

## Run from source
```
pip install -r requirements.txt
python swifthud.py
```
## Build EXE
Run `build_exe.bat`, then `sign_exe.ps1` (PowerShell as Administrator).

## Notes
- Needs Administrator rights (Windows Temp, Prefetch, Program Files).
- Self-signed signature triggers SmartScreen; use a trusted code-signing certificate for public releases.
- Use at your own risk. Close games/programs before moving them.

License: MIT

## Auto-build on GitHub
Push to `main` -> Actions tab -> "Build SwiftHUD EXE" -> download `SwiftHUD-exe` from Artifacts.

## Automatic EXE build (GitHub Actions)
Push to `main` -> Actions tab -> "Build SwiftHUD EXE" -> download `SwiftHUD-exe` artifact.
Push a tag like `v1.0.0` and the signed EXE is attached to a GitHub Release automatically.
