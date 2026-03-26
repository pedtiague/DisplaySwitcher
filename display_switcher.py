"""
Display Switcher
────────────────
• Taskbar button  — click to cycle through display modes
• System tray icon — left-click to cycle; right-click for mode menu + options
• Right-click the taskbar button (system menu) for the same mode options
• Options: start with Windows, show/hide taskbar icon (tray always visible)
"""

import subprocess, ctypes, ctypes.wintypes
import tkinter as tk
from tkinter import ttk, messagebox
import json, os, sys, threading, winreg, uuid
from PIL import Image, ImageTk, ImageDraw

try:
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

APP_ID = "DisplaySwitcher.App"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


# ── Mode definitions ──────────────────────────────────────────────────────────

MODES = [
    ("PC Screen Only",     "/internal"),
    ("Duplicate",          "/clone"),
    ("Extend",             "/extend"),
    ("Second Screen Only", "/external"),
]
MODE_NAMES = [m[0] for m in MODES]
MODE_CMD   = dict(MODES)


# ── Detect current Windows display topology ───────────────────────────────────

def detect_current_mode() -> str:
    QDC_DATABASE_CURRENT = 0x4
    np, nm = ctypes.c_uint32(), ctypes.c_uint32()
    if ctypes.windll.user32.GetDisplayConfigBufferSizes(
            QDC_DATABASE_CURRENT, ctypes.byref(np), ctypes.byref(nm)) != 0:
        return "PC Screen Only"
    paths = (ctypes.c_byte * (72 * max(np.value, 1)))()
    modes = (ctypes.c_byte * (64 * max(nm.value, 1)))()
    topo  = ctypes.c_uint32()
    if ctypes.windll.user32.QueryDisplayConfig(
            QDC_DATABASE_CURRENT,
            ctypes.byref(np), paths,
            ctypes.byref(nm), modes,
            ctypes.byref(topo)) != 0:
        return "PC Screen Only"
    return {1: "PC Screen Only", 2: "Duplicate",
            4: "Extend",         8: "Second Screen Only"}.get(topo.value, "PC Screen Only")


# ── Settings ──────────────────────────────────────────────────────────────────

_SETTINGS_DIR  = os.path.join(os.environ.get("APPDATA", ""), "DisplaySwitcher")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "start_with_windows": False,
    "show_taskbar":       True,
    "cycle_modes":        ["PC Screen Only", "Extend"],
}

def load_settings() -> dict:
    try:
        with open(_SETTINGS_FILE) as f:
            d = json.load(f)
        cm = d.get("cycle_modes", DEFAULT_SETTINGS["cycle_modes"])
        if not (isinstance(cm, list) and len(cm) == 2
                and all(c in MODE_NAMES for c in cm) and cm[0] != cm[1]):
            cm = DEFAULT_SETTINGS["cycle_modes"]
        return {
            "start_with_windows": bool(d.get("start_with_windows", False)),
            "show_taskbar":       bool(d.get("show_taskbar", True)),
            "cycle_modes":        cm,
        }
    except Exception:
        return dict(DEFAULT_SETTINGS)

def save_settings(s: dict):
    os.makedirs(_SETTINGS_DIR, exist_ok=True)
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)


# ── Start with Windows ────────────────────────────────────────────────────────

_RUN_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "DisplaySwitcher"

def _exe_path() -> str:
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)

def set_startup(enable: bool):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
    if enable:
        winreg.SetValueEx(k, _REG_NAME, 0, winreg.REG_SZ, f'"{_exe_path()}"')
    else:
        try:
            winreg.DeleteValue(k, _REG_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(k)

def get_startup() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, _REG_NAME)
        winreg.CloseKey(k)
        return True
    except FileNotFoundError:
        return False


# ── Icon drawing ──────────────────────────────────────────────────────────────

_FILL   = "#1565C0"
_SCREEN = "#0D47A1"
_BORDER = "#90CAF9"

def make_icon(mode: str, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    p   = max(2, size // 14)

    def mon(x0, y0, x1, y1, stand=True):
        d.rectangle([x0, y0, x1, y1], fill=_FILL, outline=_BORDER, width=max(1, p // 2))
        d.rectangle([x0 + p, y0 + p, x1 - p, y1 - p], fill=_SCREEN)
        if stand:
            cx = (x0 + x1) // 2
            d.rectangle([cx - p, y1, cx + p, y1 + p], fill=_BORDER)
            d.rectangle([cx - p * 2, y1 + p, cx + p * 2, y1 + p + max(1, p // 2)], fill=_BORDER)

    if mode == "PC Screen Only":
        mon(p * 2, p, size - p * 2, size - p * 3)

    elif mode == "Second Screen Only":
        # Same shape, left-side stripe to suggest it is the secondary display
        mon(p * 2, p, size - p * 2, size - p * 3)
        d.rectangle([0, p * 2, p - 1, size - p * 3], fill=_BORDER)

    elif mode == "Duplicate":
        # Two monitors, back one slightly offset
        sz = int(size * 0.72)
        off = size - sz - p
        mon(off, off, off + sz, off + sz - p * 2, stand=False)  # back
        mon(p,   p,   p + sz,  p + sz - p * 2,   stand=False)  # front
        cx = p + sz // 2
        d.rectangle([cx - p, p + sz - p * 2, cx + p, p + sz - p], fill=_BORDER)
        d.rectangle([cx - p * 2, p + sz - p, cx + p * 2, p + sz], fill=_BORDER)

    elif mode == "Extend":
        half = size // 2 - p

        def small_mon(x0, x1):
            mon(x0, p, x1, size - p * 3, stand=False)
            cx = (x0 + x1) // 2
            d.rectangle([cx - p, size - p * 3, cx + p, size - p * 2], fill=_BORDER)
            d.rectangle([cx - p * 2, size - p * 2, cx + p * 2, size - p + 1], fill=_BORDER)

        small_mon(0, half)
        small_mon(size - half, size)
        ay = size // 2
        d.line([(half + 1, ay), (size - half - 1, ay)], fill=_BORDER, width=max(1, p // 2))
        d.polygon([(size - half - 1, ay), (size - half - p - 1, ay - p + 1),
                   (size - half - p - 1, ay + p - 1)], fill=_BORDER)

    return img


# ── Win32 HICON helpers ───────────────────────────────────────────────────────

class _BMI(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPPM", ctypes.c_int32),
                ("biYPPM", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]

class _IIFO(ctypes.Structure):
    _fields_ = [("fIcon", ctypes.c_bool), ("xHot", ctypes.c_uint32),
                ("yHot", ctypes.c_uint32), ("hMask", ctypes.c_void_p),
                ("hColor", ctypes.c_void_p)]

def pil_to_hicon(img: Image.Image) -> int:
    img = img.convert("RGBA"); w, h = img.size; raw = img.tobytes("raw", "BGRA")
    hdc = ctypes.windll.user32.GetDC(None)
    bmi = _BMI(); bmi.biSize = ctypes.sizeof(_BMI); bmi.biWidth = w
    bmi.biHeight = -h; bmi.biPlanes = 1; bmi.biBitCount = 32; bmi.biSizeImage = len(raw)
    ppv = ctypes.c_void_p()
    hbmc = ctypes.windll.gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(ppv), None, 0)
    ctypes.memmove(ppv, raw, len(raw))
    ctypes.windll.user32.ReleaseDC(None, hdc)
    hbmm = ctypes.windll.gdi32.CreateBitmap(w, h, 1, 1, None)
    ii = _IIFO(); ii.fIcon = True; ii.hMask = hbmm; ii.hColor = hbmc
    hicon = ctypes.windll.user32.CreateIconIndirect(ctypes.byref(ii))
    ctypes.windll.gdi32.DeleteObject(hbmm); ctypes.windll.gdi32.DeleteObject(hbmc)
    return hicon

def send_icon(hwnd: int, hicon: int):
    sm = ctypes.windll.user32.SendMessageW
    sm(hwnd, 0x0080, 0, hicon)
    sm(hwnd, 0x0080, 1, hicon)


# ── ITaskbarList3 overlay (pinned button badge) ───────────────────────────────

class _GUID(ctypes.Structure):
    _fields_ = [("D1", ctypes.c_ulong), ("D2", ctypes.c_ushort),
                ("D3", ctypes.c_ushort), ("D4", ctypes.c_ubyte * 8)]

def _mkguid(s):
    b = uuid.UUID(s).bytes_le; g = _GUID()
    ctypes.memmove(ctypes.addressof(g), b, 16); return g

_CLS = _mkguid("56FDF344-FD6D-11d0-958A-006097C9A090")
_IID = _mkguid("EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF")

def tbl_create():
    ctypes.windll.ole32.CoInitialize(None)
    ptr = ctypes.c_void_p()
    if ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(_CLS), None, 1, ctypes.byref(_IID), ctypes.byref(ptr)) != 0:
        return None
    vt = ctypes.cast(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0],
                     ctypes.POINTER(ctypes.c_void_p))
    ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vt[3])(ptr)
    return ptr

def tbl_overlay(tbl, hwnd: int, hicon: int, desc: str):
    if not tbl: return
    vt = ctypes.cast(ctypes.cast(tbl, ctypes.POINTER(ctypes.c_void_p))[0],
                     ctypes.POINTER(ctypes.c_void_p))
    ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_wchar_p)(vt[18])(tbl, hwnd, hicon, desc)




# ── Application ───────────────────────────────────────────────────────────────

class DisplaySwitcher:

    def __init__(self):
        self.settings     = load_settings()
        self.current_mode = detect_current_mode()
        self._closing    = False
        self._started    = False
        self._hicon      = None
        self._hicon_over = None
        self._tbl        = None
        self._tray       = None

        # ── Tkinter window ────────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.geometry("1x1+-32000+-32000")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.bind("<Map>", self._on_map)

        self._refresh_tk_icon()
        self.root.after(50,  self._post_init)

    # ── Initialisation ────────────────────────────────────────────────────────

    def _post_init(self):
        self._apply_visibility()
        self.root.after(150, self._late_init)

    def _late_init(self):
        # Each step is isolated — a failure in one must not block the rest.
        try:
            self._tbl = tbl_create()
            self._update_overlay()
        except Exception:
            pass

        try:
            if HAS_TRAY:
                self._start_tray()
        except Exception:
            pass

        # Must always be reached so taskbar clicks work.
        self._started = True

    # ── Visibility ────────────────────────────────────────────────────────────

    def _apply_visibility(self):
        if self.settings["show_taskbar"]:
            if self.root.state() == "withdrawn":
                # Temporarily suppress <Map> so deiconify doesn't trigger _on_map
                self.root.unbind("<Map>")
                self.root.deiconify()
                self.root.iconify()
                self.root.after(300, lambda: self.root.bind("<Map>", self._on_map))
            else:
                self.root.iconify()
        else:
            self.root.withdraw()

    # ── Mode switching ────────────────────────────────────────────────────────

    def set_mode(self, mode_name: str):
        if mode_name not in MODE_CMD:
            return
        self.current_mode = mode_name
        subprocess.Popen(["DisplaySwitch.exe", MODE_CMD[mode_name]])
        self._refresh_all()

    def _cycle_mode(self):
        cycle = self.settings["cycle_modes"]
        try:
            idx = cycle.index(self.current_mode)
            next_mode = cycle[(idx + 1) % len(cycle)]
        except ValueError:
            next_mode = cycle[0]
        self.set_mode(next_mode)

    # ── Taskbar click ─────────────────────────────────────────────────────────

    def _on_map(self, _event=None):
        """<Map> fires when the minimised window is restored (taskbar click)."""
        if not self._started or self._closing:
            return
        self._cycle_mode()
        self.root.after(0, self.root.iconify)

    # ── Icon refresh ──────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_tk_icon()
        self._update_overlay()
        self._refresh_tray_icon()

    def _refresh_tk_icon(self):
        mode  = self.current_mode
        label = f"Display — {mode}"
        self.root.title(label)

        img   = make_icon(mode, 64)
        photo = ImageTk.PhotoImage(img)
        self._photo = photo          # prevent GC
        self.root.iconphoto(True, photo)

        hwnd = self.root.winfo_id()
        if hwnd:
            if self._hicon:
                ctypes.windll.user32.DestroyIcon(self._hicon)
            self._hicon = pil_to_hicon(img)
            send_icon(hwnd, self._hicon)

    def _update_overlay(self):
        """Overlay badge for pinned taskbar buttons (the only API that works there)."""
        hwnd = self.root.winfo_id()
        if not hwnd or not self._tbl:
            return
        if self._hicon_over:
            ctypes.windll.user32.DestroyIcon(self._hicon_over)
            self._hicon_over = None
        if self.current_mode != "PC Screen Only":
            self._hicon_over = pil_to_hicon(make_icon(self.current_mode, 32))
            tbl_overlay(self._tbl, hwnd, self._hicon_over, self.current_mode)
        else:
            tbl_overlay(self._tbl, hwnd, None, "")

    # ── Tray icon ─────────────────────────────────────────────────────────────

    def _start_tray(self):
        img  = make_icon(self.current_mode, 64)
        menu = self._build_tray_menu()
        self._tray = pystray.Icon("DisplaySwitcher", img,
                                  f"Display — {self.current_mode}", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _build_tray_menu(self):
        # pystray calls action callbacks with (icon, item) — use *_ to accept any args.
        def mode_cb(name):
            def cb(*_): self.root.after(0, lambda: self.set_mode(name))
            return cb

        def mode_item(name):
            return pystray.MenuItem(
                name,
                mode_cb(name),
                checked=lambda item, n=name: self.current_mode == n,
            )

        return pystray.Menu(
            pystray.MenuItem(
                "Cycle Mode", lambda *_: self.root.after(0, self._cycle_mode),
                default=True, visible=False,
            ),
            *[mode_item(n) for n in MODE_NAMES],
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Options…", lambda *_: self.root.after(0, self.open_options)),
            pystray.MenuItem("Quit",     lambda *_: self.root.after(0, self._quit)),
        )

    def _refresh_tray_icon(self):
        if not self._tray:
            return
        self._tray.icon  = make_icon(self.current_mode, 64)
        self._tray.title = f"Display — {self.current_mode}"
        self._tray.update_menu()

    # ── Options window ────────────────────────────────────────────────────────

    def open_options(self):
        # If already open, bring to front
        if hasattr(self, "_opt_win") and self._opt_win.winfo_exists():
            self._opt_win.lift()
            return
        OptionsWindow(self)

    # ── Quit ──────────────────────────────────────────────────────────────────

    def _quit(self):
        self._closing = True
        if self._tray:
            self._tray.stop()
        self.root.destroy()

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ── Options window ────────────────────────────────────────────────────────────

class OptionsWindow:

    def __init__(self, app: DisplaySwitcher):
        self.app = app

        win = tk.Toplevel(app.root)
        app._opt_win = win   # store Toplevel so open_options can call winfo_exists()
        win.title("Display Switcher — Options")
        win.geometry("340x230")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self.win = win

        pad = {"padx": 16, "pady": 6}

        # ── Start with Windows ────────────────────────────────────────────────
        self._startup_var = tk.BooleanVar(value=get_startup())
        ttk.Checkbutton(win, text="Start with Windows",
                        variable=self._startup_var).pack(anchor="w", **pad)

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # ── Taskbar visibility ────────────────────────────────────────────────
        self._taskbar_var = tk.BooleanVar(value=app.settings["show_taskbar"])
        ttk.Checkbutton(win, text="Show icon in taskbar",
                        variable=self._taskbar_var).pack(anchor="w", **pad)

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # ── Click-cycle modes ─────────────────────────────────────────────────
        cycle = app.settings["cycle_modes"]
        cycle_frame = ttk.Frame(win)
        cycle_frame.pack(fill="x", padx=16, pady=6)
        ttk.Label(cycle_frame, text="Click cycles between:").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self._cycle_a = tk.StringVar(value=cycle[0])
        self._cycle_b = tk.StringVar(value=cycle[1])
        ttk.Combobox(cycle_frame, textvariable=self._cycle_a,
                     values=MODE_NAMES, state="readonly", width=16).grid(
            row=1, column=0, padx=(0, 4))
        ttk.Label(cycle_frame, text="↔").grid(row=1, column=1, padx=4)
        ttk.Combobox(cycle_frame, textvariable=self._cycle_b,
                     values=MODE_NAMES, state="readonly", width=16).grid(
            row=1, column=2, padx=(4, 0))

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Button(btn_frame, text="Save",   command=self._save).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="right")

    def _save(self):
        startup      = self._startup_var.get()
        show_taskbar = self._taskbar_var.get()
        mode_a       = self._cycle_a.get()
        mode_b       = self._cycle_b.get()

        if mode_a == mode_b:
            tk.messagebox.showwarning(
                "Invalid selection",
                "The two cycle modes must be different.",
                parent=self.win,
            )
            return

        set_startup(startup)

        old_taskbar = self.app.settings["show_taskbar"]
        self.app.settings["start_with_windows"] = startup
        self.app.settings["show_taskbar"]        = show_taskbar
        self.app.settings["cycle_modes"]         = [mode_a, mode_b]
        save_settings(self.app.settings)

        if show_taskbar != old_taskbar:
            self.app._apply_visibility()

        self.win.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    DisplaySwitcher().run()
