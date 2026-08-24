import os
import sys
import json
import shutil
import ssl
import urllib.parse
import urllib.request


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

    # 2. Check local tools directory and root directory
    for rel_path in [os.path.join("tools", "ffmpeg.exe"), "ffmpeg.exe"]:
        local_path = os.path.join(get_root_dir(), rel_path)
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


def clean_youtube_url(url: str) -> str:
    """Strips mix/playlist parameters to ensure single-video metadata is fetched."""
    if "youtube.com/watch" in url and "v=" in url:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    return url


def is_youtube_url(text: str) -> bool:
    """Returns True when the text looks like a YouTube link."""
    return "youtube.com/" in text or "youtu.be/" in text


def format_display_title(title: str, uploader: str) -> str:
    """Prefixes the channel/artist name unless it is already part of the title."""
    if uploader and uploader.lower() not in title.lower():
        return f"{uploader} - {title}"
    return title


def insecure_ssl_context() -> ssl.SSLContext:
    """Creates an SSL context tolerant of certificate issues on end-user machines."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_oembed_title(clean_url: str) -> str | None:
    """
    Fetches a video title through YouTube's lightweight oEmbed JSON API (~50ms).
    Returns the formatted display title, or None when unavailable.
    """
    oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url, safe='')}&format=json"
    req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=3, context=insecure_ssl_context()) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None
    title = data.get('title', '')
    if not title:
        return None
    return format_display_title(title, data.get('author_name', ''))


def image_to_jpeg_bytes(raw_bytes: bytes) -> bytes:
    """Re-encodes WebP/PNG/etc. image data into genuine JPEG bytes via the Qt image engine."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage

    qimg = QImage()
    if qimg.loadFromData(raw_bytes):
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        if qimg.save(buf, "JPEG"):
            return buf.data().data()
    return raw_bytes
