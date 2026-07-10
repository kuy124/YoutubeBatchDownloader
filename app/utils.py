import os
import sys
import shutil

def get_root_dir() -> str:
    """Returns the root directory of the application, handling PyInstaller environment."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_ffmpeg_path() -> str:
    """Returns the absolute path to ffmpeg.exe (bundled, local workspace, or global system path)."""
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, "tools", "ffmpeg.exe")
        if os.path.exists(bundled_path):
            return bundled_path

    # 2. Check developer workspace tools folder
    local_path = os.path.join(get_root_dir(), "tools", "ffmpeg.exe")
    if os.path.exists(local_path):
        return local_path
    
    # 3. Check system PATH globally
    system_path = shutil.which('ffmpeg')
    if system_path:
        return system_path
        
    return ""

def get_icon_path() -> str:
    """Returns the absolute path to icon.ico (bundled or local workspace)."""
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_icon = os.path.join(sys._MEIPASS, "icon.ico")
        if os.path.exists(bundled_icon):
            return bundled_icon

    # 2. Check developer workspace
    local_icon = os.path.join(get_root_dir(), "icon.ico")
    if os.path.exists(local_icon):
        return local_icon
        
    return ""

def format_speed(speed_bytes) -> str:
    if speed_bytes is None:
        return "0 KB/s"
    speed = speed_bytes / 1024
    if speed > 1024:
        return f"{speed / 1024:.2f} MB/s"
    return f"{speed:.2f} KB/s"