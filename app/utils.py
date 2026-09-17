import os
import re
import sys
import json
import shutil
import ssl
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse


APP_NAME = "YouTubeBatchDownloader"


_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_FORMAT_EXTENSIONS = {
    "Best Quality (MKV)": ".mkv",
    "MP4 Video": ".mp4",
    "WEBM Video": ".webm",
    "AVI Video": ".avi",
    "MOV Video": ".mov",
    "MP3 Audio": ".mp3",
    "M4A Audio": ".m4a",
    "WAV Audio": ".wav",
    "FLAC Audio": ".flac",
    "AAC Audio": ".aac",
    "OPUS Audio": ".opus",
}


def get_install_dir() -> str:
    """Returns the directory containing the source tree or installed executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_root_dir() -> str:
    """Backward-compatible alias for the install/source directory."""
    return get_install_dir()


def get_data_dir() -> str:
    """Returns the writable per-user data directory for packaged builds.

    Source mode intentionally keeps data beside the checkout so the developer
    workflow remains unchanged.  Packaged builds keep mutable files out of the
    install directory, which makes upgrades and uninstall cleanup predictable.
    """
    if not getattr(sys, 'frozen', False):
        return get_install_dir()
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(local_app_data, APP_NAME)


def _copy_missing_tree(source: str, destination: str) -> None:
    """Copies legacy data without replacing anything already in the new store."""
    if os.path.isdir(source):
        os.makedirs(destination, exist_ok=True)
        for entry in os.scandir(source):
            target = os.path.join(destination, entry.name)
            if entry.is_dir(follow_symlinks=False):
                _copy_missing_tree(entry.path, target)
            elif entry.is_file(follow_symlinks=False) and not os.path.exists(target):
                shutil.copy2(entry.path, target)
    elif os.path.isfile(source) and not os.path.exists(destination):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)


def migrate_legacy_data() -> bool:
    """Migrates mutable files from an older portable install once, safely."""
    if not getattr(sys, 'frozen', False):
        return False
    install_dir = get_install_dir()
    data_dir = get_data_dir()
    if os.path.normcase(os.path.abspath(install_dir)) == os.path.normcase(os.path.abspath(data_dir)):
        return False
    marker = os.path.join(data_dir, ".legacy-migration-complete")
    if os.path.exists(marker):
        return False

    try:
        os.makedirs(data_dir, exist_ok=True)
        for name in ("settings.json", "logs", "runtime"):
            source = os.path.join(install_dir, name)
            destination = os.path.join(data_dir, name)
            if os.path.exists(source):
                _copy_missing_tree(source, destination)
        with open(marker, "w", encoding="utf-8") as marker_file:
            marker_file.write("migrated")
        return True
    except (OSError, shutil.Error):
        return False


def get_ffmpeg_path() -> str:
    """Returns the absolute path to ffmpeg.exe (bundled, local workspace, or global system path)."""
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, "tools", "ffmpeg.exe")
        if os.path.exists(bundled_path):
            return bundled_path

    # 2. Check local tools directory and root directory
    for rel_path in [os.path.join("tools", "ffmpeg.exe"), "ffmpeg.exe"]:
        local_path = os.path.join(get_install_dir(), rel_path)
        if os.path.exists(local_path):
            return local_path

    # 3. Check system PATH globally
    system_path = shutil.which('ffmpeg')
    if system_path:
        return system_path

    return ""


def get_aria2_path() -> str:
    """Returns the absolute path to aria2c.exe (bundled, local workspace, or global system path)."""
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, "tools", "aria2c.exe")
        if os.path.exists(bundled_path):
            return bundled_path

    # 2. Check local tools directory and root directory
    for rel_path in [os.path.join("tools", "aria2c.exe"), "aria2c.exe"]:
        local_path = os.path.join(get_install_dir(), rel_path)
        if os.path.exists(local_path):
            return local_path

    # 3. Check system PATH globally
    system_path = shutil.which('aria2c')
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
    local_icon = os.path.join(get_install_dir(), "icon.ico")
    if os.path.exists(local_icon):
        return local_icon

    return ""


def clean_youtube_url(url: str) -> str:
    """Strips mix/playlist parameters to ensure single-video metadata is fetched."""
    if "youtube.com/watch" in url and "v=" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    return url


def is_youtube_url(text: str) -> bool:
    """Returns True when the text looks like a YouTube link."""
    return "youtube.com/" in text or "youtu.be/" in text


def extract_http_links(text: str) -> list:
    """Pulls every http(s) URL out of arbitrary pasted/dropped text, preserving order."""
    links = []
    for token in re.split(r'\s+', (text or '').strip()):
        token = token.strip().strip('<>"\'').rstrip(',;)];')
        if token[:7].lower() == "http://" or token[:8].lower() == "https://":
            links.append(token)
    return links


def output_extension_for_format(format_name: str) -> str:
    """Returns the final extension produced by a configured output format."""
    return _FORMAT_EXTENSIONS.get(format_name, "")


def sanitize_output_stem(value: str, format_name: str = "", max_length: int = 180) -> str:
    """Normalizes a user-provided filename stem for a portable Windows download."""
    stem = (value or "").strip()
    expected_ext = output_extension_for_format(format_name)
    if expected_ext and stem.lower().endswith(expected_ext):
        stem = stem[:-len(expected_ext)]

    stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', stem)
    stem = stem.rstrip(' .')
    if not stem:
        return ""

    if stem.split('.', 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        stem += "_"

    if len(stem) > max_length:
        stem = stem[:max_length].rstrip(' .')
    return stem


def escape_yt_dlp_template_literal(value: str) -> str:
    """Escapes percent signs before inserting literal text into a yt-dlp template."""
    return (value or "").replace('%', '%%')


def format_display_title(title: str, uploader: str) -> str:
    """Prefixes the channel/artist name unless it is already part of the title."""
    if uploader and uploader.lower() not in title.lower():
        return f"{uploader} - {title}"
    return title


def resolve_uploader(info_dict: dict) -> str:
    """Picks the best artist attribution from a yt-dlp info dict."""
    return info_dict.get('artist') or info_dict.get('uploader') or info_dict.get('creator') or info_dict.get('channel') or ''


def format_hms(total_seconds) -> str:
    """Formats a duration in seconds as MM:SS or HH:MM:SS."""
    total_seconds = int(total_seconds)
    mins, secs = divmod(total_seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def format_elapsed_words(total_seconds: int) -> str:
    """Formats a duration in seconds as human-readable words, e.g. '2 minutes and 5 seconds'."""
    mins, secs = divmod(int(total_seconds), 60)
    if mins > 0:
        return f"{mins} minute{'s' if mins != 1 else ''} and {secs} second{'s' if secs != 1 else ''}"
    return f"{secs} second{'s' if secs != 1 else ''}"


def insecure_ssl_context() -> ssl.SSLContext:
    """Creates an SSL context tolerant of certificate issues on end-user machines."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_audio_boost_filter(boost_str: str) -> str | None:
    """
    Builds an FFmpeg audio filter chain that boosts the volume and then
    soft-limits the peaks, preventing the hard clipping distortion of a raw
    volume boost. Returns None when no boost is requested.
    """
    match = re.search(r'(\d+)%', boost_str or '')
    vol_pct = int(match.group(1)) if match else 100
    if vol_pct <= 100:
        return None
    return (
        f"volume={vol_pct / 100.0:.2f}"
        # level=disabled stops alimiter re-normalizing the signal back to full scale
        ",alimiter=level_in=1:level_out=1:limit=0.95:attack=5:release=80:level=disabled"
    )


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
