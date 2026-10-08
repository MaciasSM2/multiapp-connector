import os
from pathlib import Path

# Base Paths
WORKSPACE_DIR = Path(r"c:\Users\Sebastian Macias\Documents\0. Programacion\Conector de aplicativos")
OUTPUT_DIR = WORKSPACE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ChamVa configuration
CHAMVA_APP_DIR = Path(r"C:\Users\Sebastian Macias\AppData\Local\ChamVa")
CHAMVA_EXE_PATH = CHAMVA_APP_DIR / "chamva.exe"
CHAMVA_FFMPEG_PATH = CHAMVA_APP_DIR / "ffmpeg" / "ffmpeg.exe"
CHAMVA_FFPROBE_PATH = CHAMVA_APP_DIR / "ffmpeg" / "ffprobe.exe"
CHAMVA_CDP_PORT = 9333
CHAMVA_DATA_DIR = Path(r"C:\Users\Sebastian Macias\AppData\Local\com.chamva.editor")

# Krita configuration
KRITA_APP_DIR = Path(r"C:\Program Files\Krita (x64)")
KRITA_EXE_PATH = KRITA_APP_DIR / "bin" / "krita.exe"
KRITA_PORT = 52150

# Server settings
SERVER_NAME = "multiapp-connector"
SERVER_VERSION = "1.1.0"
