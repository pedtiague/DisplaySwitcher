"""Generates icon.ico used by PyInstaller to embed into the exe."""
from display_switcher import make_icon

img = make_icon("PC Screen Only", size=256)

# Save as .ico with multiple resolutions so Windows picks the best size
img.save(
    "icon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
)

print("icon.ico generated.")
