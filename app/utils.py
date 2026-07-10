import os
import sys

def get_root_dir() -> str:
    """Returns the root directory of the application, handling PyInstaller environment."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_ffmpeg_path() -> str:
    """Returns the absolute path to ffmpeg.exe if it exists."""
    path = os.path.join(get_root_dir(), "tools", "ffmpeg.exe")
    return path if os.path.exists(path) else ""

def format_speed(speed_bytes) -> str:
    if speed_bytes is None:
        return "0 KB/s"
    speed = speed_bytes / 1024
    if speed > 1024:
        return f"{speed / 1024:.2f} MB/s"
    return f"{speed:.2f} KB/s"