# DisplaySwitcher

A lightweight Windows system tray + taskbar app that lets you instantly toggle your display projection mode between **PC Screen Only** and **Extend** — with a single click.

---

## The Problem

When a primary monitor is shared between two machines (e.g. switching the monitor's physical input), the Windows display projection settings need to be changed frequently. The built-in Windows shortcut (`Win + P`) requires keyboard access, and the Settings app is buried too deep for quick use. This tool makes the switch a single taskbar click away.

---

## Features

- **Taskbar presence** — appears as a regular open-application button (not just a tray icon), visible and clickable from both machines sharing the monitor
- **System tray icon** — always-visible tray icon showing the current display mode
- **Left-click to toggle** — cycles between *PC Screen Only* and *Extend*
- **Right-click tray menu** — force any of the 4 Windows display modes:
  - PC Screen Only
  - Duplicate
  - Extend
  - Second Screen Only
- **Live icon updates** — both taskbar and tray icons update instantly to reflect the current mode
- **Options panel** (via tray right-click → Options…):
  - Start with Windows toggle
  - Show / hide the taskbar icon (tray is always visible)
- **Settings persist** across sessions (stored in `%APPDATA%\DisplaySwitcher\settings.json`)

---

## Display Mode Icons

| Mode | Icon |
|------|------|
| PC Screen Only | Single blue monitor |
| Duplicate | Two blue monitors (mirrored) |
| Extend | Two blue monitors (side by side, extended) |
| Second Screen Only | Single blue monitor (right side) |

---

## Requirements

- Windows 10 / 11
- Python 3.9+ (only needed to run from source or build the exe)
- Dependencies: `Pillow`, `pystray`

---

## Running from Source

```bash
pip install -r requirements.txt
python display_switcher.py
```

Or use the included launcher:

```bash
run.bat
```

---

## Building the Standalone Executable

Run the build script (installs dependencies, generates the icon, and packages everything into a single `.exe`):

```bash
build_exe.bat
```

The output will be at `dist\DisplaySwitcher.exe`.

> **Note:** If the build fails with a `PermissionError`, make sure `dist\DisplaySwitcher.exe` is not currently running.

---

## Usage

1. Launch `DisplaySwitcher.exe` (or `python display_switcher.py`)
2. The app appears as a button in your taskbar and as a tray icon
3. **Left-click** the taskbar button or tray icon to toggle between *PC Screen Only* and *Extend*
4. **Right-click** the tray icon to:
   - Force a specific display mode
   - Open Options
   - Quit
5. Pin to taskbar for persistent access across sessions

> **Pinned icon note:** Windows 11 does not dynamically update the icon of a *pinned* taskbar shortcut. The icon will update correctly when the app is running and unpinned. The tray icon always reflects the current mode accurately.

---

## Start with Windows

In the Options window, enable **"Start with Windows"** to have DisplaySwitcher launch automatically on login. This adds an entry to:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

---

## File Structure

```
DisplaySwitcher/
├── display_switcher.py   # Main application
├── generate_icon.py      # Generates icon.ico from the app's icon drawing code
├── requirements.txt      # Python dependencies
├── build_exe.bat         # One-click build script (PyInstaller)
├── run.bat               # Run from source shortcut
└── icon.ico              # App icon (generated)
```

---

## Technical Details

- **UI framework:** `tkinter` — a hidden 1×1 window iconified to the taskbar; the `<Map>` event fires when the user clicks the taskbar button, triggering the mode toggle
- **Tray icon:** `pystray` running in a daemon thread
- **Display switching:** Windows `DisplaySwitch.exe` CLI (`/internal`, `/clone`, `/extend`, `/external`)
- **Mode detection:** Win32 `QueryDisplayConfig` API to read the current topology
- **Icons:** Drawn programmatically with `Pillow` (RGBA), converted to `HICON` via `CreateDIBSection` + `CreateIconIndirect`
- **Taskbar overlay:** `ITaskbarList3::SetOverlayIcon` for a mode badge on the taskbar button
- **Packaging:** PyInstaller `--onefile --windowed`

---

## License

MIT
