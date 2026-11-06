import contextlib
import os
import re
import sys
import json
import shutil
import ssl
import subprocess
import tempfile
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from .platform_compat import tool_name, user_data_dir, external_tool_env


APP_NAME = "YouTubeBatchDownloader"

# Placeholder shown in the title preview column for collection links, which
# resolve into many rows only when the queue is built.
PLAYLIST_PREVIEW_LABEL = "Playlist (expands on Add to Queue)"


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
    return user_data_dir()


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
    """Find a runnable FFmpeg, preferring distro binaries on Linux."""
    executable = tool_name("ffmpeg")
    candidates = []
    system_path = shutil.which('ffmpeg')
    if sys.platform.startswith("linux") and system_path:
        candidates.append(system_path)
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, "tools", executable)
        candidates.append(bundled_path)

    # 2. Check local tools directory and root directory
    for rel_path in [os.path.join("tools", executable), executable]:
        local_path = os.path.join(get_install_dir(), rel_path)
        candidates.append(local_path)

    # 3. Check system PATH globally
    if system_path:
        candidates.append(system_path)

    for path in dict.fromkeys(candidates):
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            continue
        try:
            result = subprocess.run(
                [path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5, env=external_tool_env(),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0 and result.stdout.startswith(b'ffmpeg version'):
                return os.path.abspath(path)
        except (OSError, subprocess.TimeoutExpired):
            continue

    return ""


def get_aria2_path() -> str:
    """Returns the absolute path to aria2c (bundled, local workspace, or global system path)."""
    executable = tool_name("aria2c")
    # 1. Check if running inside PyInstaller virtual unpacked environment (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, "tools", executable)
        if os.path.exists(bundled_path):
            return bundled_path

    # 2. Check local tools directory and root directory
    for rel_path in [os.path.join("tools", executable), executable]:
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


def clean_youtube_url(url: str, keep_playlist: bool = False) -> str:
    """Strips mix/playlist parameters to ensure single-video metadata is fetched.

    keep_playlist preserves a genuine playlist id so the queue can expand it;
    auto-generated Mix ids (RD...) are always dropped because they are endless.
    """
    if "youtube.com/watch" in url and "v=" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            base = f"https://www.youtube.com/watch?v={qs['v'][0]}"
            list_id = (qs.get('list') or [''])[0]
            if keep_playlist and list_id and not is_mix_playlist(list_id):
                return f"{base}&list={list_id}"
            return base
    return url


def is_mix_playlist(list_id: str) -> bool:
    """True for YouTube's endless auto-generated Mix/Radio playlists."""
    return (list_id or '').upper().startswith('RD')


def extract_playlist_id(url: str) -> str:
    """Returns the `list=` value carried by a URL, or an empty string."""
    try:
        return (parse_qs(urlparse(url or '').query).get('list') or [''])[0]
    except ValueError:
        return ''


def is_expandable_playlist(url: str) -> bool:
    """True when a link addresses a collection rather than a single video."""
    url = url or ''
    lowered = url.lower()
    if any(marker in lowered for marker in (
        '/playlist', '/channel/', '/user/', '/c/', '/@', '?tab=', '&tab=',
        '/videos', '/streams', '/shorts',
    )):
        return True
    list_id = extract_playlist_id(url)
    return bool(list_id) and not is_mix_playlist(list_id)


def playlist_url_for_expansion(url: str) -> str:
    """Rewrites a watch+list link to its canonical playlist URL.

    yt-dlp resolves a watch URL through the watch page, so one unavailable
    anchor video aborts expansion of an otherwise healthy playlist.
    """
    list_id = extract_playlist_id(url)
    if list_id and not is_mix_playlist(list_id):
        return f"https://www.youtube.com/playlist?list={list_id}"
    return url


def parse_rate_limit(text) -> int | None:
    """Converts a display string such as '5 MB/s' into bytes per second."""
    if not text:
        return None
    match = re.search(r'([\d.]+)\s*(KB|MB|GB|K|M|G)?', str(text), re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or 'MB').upper()
    multiplier = {
        'K': 1024, 'KB': 1024,
        'M': 1024 ** 2, 'MB': 1024 ** 2,
        'G': 1024 ** 3, 'GB': 1024 ** 3,
    }[unit]
    rate = int(value * multiplier)
    return rate if rate > 0 else None


def parse_subtitle_langs(text) -> list:
    """Normalizes a subtitle language field into a yt-dlp language list."""
    raw = (text or '').strip()
    if not raw or raw.lower() in ('auto', 'all', '*'):
        return ['all']
    return [part.strip() for part in re.split(r'[,\s]+', raw) if part.strip()]


def build_cookies_options(mode: str, browser: str = "", cookie_file: str = "") -> dict:
    """Builds yt-dlp credential options for the selected cookies source."""
    mode = (mode or 'Disabled').strip()
    if mode == 'From browser':
        name = (browser or 'chrome').strip().lower()
        return {'cookiesfrombrowser': (name, None, None, None)}
    if mode == 'cookies.txt file':
        path = (cookie_file or '').strip()
        if path and os.path.isfile(path):
            return {'cookiefile': path}
    return {}


# YouTube answers "The page needs to be reloaded" when a request carries these
# without the SAPISIDHASH authorization header only the browser can produce, and
# yt-dlp sends the cookies but never computes that hash. The rejection comes back
# as an empty format list, which the app reports as "Requested format is not
# available" or "Video unavailable" - nowhere near the real cause. Only the
# youtube.com copies matter; the google.com ones are left alone.
YOUTUBE_SAPISID_NAMES = frozenset({'SAPISID', '__Secure-1PAPISID', '__Secure-3PAPISID'})


def _is_rejected_cookie_line(line: str) -> bool:
    fields = line.split('\t')
    if len(fields) != 7 or fields[5] not in YOUTUBE_SAPISID_NAMES:
        return False
    domain = fields[0].removeprefix('#HttpOnly_').lstrip('.').lower()
    return domain == 'youtube.com' or domain.endswith('.youtube.com')


def write_cookie_copy(source: str, destination: str) -> int:
    """Copies a Netscape cookie file, dropping rows YouTube would reject."""
    dropped = 0
    with open(source, 'rb') as reader, open(destination, 'wb') as writer:
        for raw in reader:
            if _is_rejected_cookie_line(raw.decode('utf-8', 'replace').rstrip('\r\n')):
                dropped += 1
                continue
            writer.write(raw)
    return dropped


@contextlib.contextmanager
def private_cookiefile(cookiefile: str | None):
    """Yields a throwaway, YouTube-safe copy of a cookie file for one yt-dlp run.

    yt-dlp dumps its jar back into whatever 'cookiefile' names, and YouTube
    rotates __Secure-1PSIDTS per session. Sharing one file across the pool let a
    task persist a token that was already dead for everyone else, so the copy is
    what gets written back and the shared file stays exactly as the browser sent it.
    """
    if not cookiefile or not os.path.isfile(cookiefile):
        yield cookiefile
        return
    descriptor, copy = tempfile.mkstemp(prefix="ytdlp-cookies-", suffix=".txt")
    os.close(descriptor)
    try:
        write_cookie_copy(cookiefile, copy)
        yield copy
    finally:
        try:
            os.remove(copy)
        except OSError:
            pass


def js_runtime_options() -> dict:
    """Returns the yt-dlp params that let it solve YouTube's signature challenge.

    yt-dlp runs the challenge in an external JavaScript runtime and enables only
    Deno by default. On a machine with Node but no Deno the challenge goes
    unsolved, YouTube answers with storyboard images only, and the audio selector
    reports "Requested format is not available" for videos that play fine in a
    browser. Naming every runtime lets yt-dlp use whichever one is installed; a
    missing one is skipped silently.

    A fresh dict each call because yt-dlp drops unsupported names in place.
    """
    return {'js_runtimes': {name: {} for name in ('deno', 'node', 'bun', 'quickjs')}}


_COOKIE_ERROR_HINTS = (
    # Chrome/Edge/Brave on Windows protect cookies with App-Bound Encryption,
    # which yt-dlp cannot decrypt: https://github.com/yt-dlp/yt-dlp/issues/10927
    (('DPAPI', '10927'),
     "Windows blocks reading this browser's cookies (App-Bound Encryption). "
     "Try Firefox under 'From browser', or select a cookies.txt file. Cookies are optional for public videos."),
    (('Could not copy', '7271'),
     "The browser is holding its cookie database open. Close it completely, then try again."),
)


def explain_cookie_failure(message: str) -> str | None:
    """Translates yt-dlp cookie errors into an action the user can take."""
    text = message or ''
    for markers, hint in _COOKIE_ERROR_HINTS:
        if any(marker in text for marker in markers):
            return hint
    return None


_SUBTITLE_EMBED_CONTAINERS = {'mp4', 'mkv', 'mov', 'webm'}


def build_subtitle_options(mode: str, langs, container: str) -> dict:
    """Builds subtitle download options plus the matching postprocessors.

    Returns {'opts': {...}, 'postprocessors': [...]} so the caller can merge the
    postprocessors into the format-specific chain instead of overwriting it.
    """
    mode = (mode or 'Off').strip()
    if mode == 'Off':
        return {'opts': {}, 'postprocessors': []}

    languages = parse_subtitle_langs(langs)
    opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': languages,
        'subtitlesformat': 'srt/best',
    }
    if mode == 'Embed in video' and (container or '').lower() in _SUBTITLE_EMBED_CONTAINERS:
        return {'opts': opts, 'postprocessors': [{'key': 'FFmpegEmbedSubtitle'}]}
    if mode == 'Embed in video':
        # Containers such as AVI cannot hold a subtitle track, so fall back to a
        # sidecar rather than silently dropping the captions.
        opts.pop('subtitlesformat', None)
        return {'opts': opts, 'postprocessors': []}
    return {
        'opts': opts,
        'postprocessors': [{'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}],
    }


def find_existing_output(download_path: str, title: str, format_name: str) -> str:
    """Returns a complete file already in the download folder for this title."""
    if not download_path or not title:
        return ""
    stem = sanitize_output_stem(title, format_name)
    if not stem:
        return ""
    extension = output_extension_for_format(format_name)
    if not extension:
        return ""
    candidate = os.path.join(download_path, stem + extension)
    try:
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate
    except OSError:
        return ""
    return ""


def is_youtube_url(text: str) -> bool:
    """Returns True when the text looks like a YouTube link."""
    return "youtube.com/" in text or "youtu.be/" in text


def extract_http_links(text: str) -> list:
    """Pulls every http(s) URL out of arbitrary pasted/dropped text, preserving order."""
    links = []
    for token in re.split(r'\s+', (text or '').strip()):
        token = token.strip().rstrip(',;)];').strip('<>"\'').rstrip(',;)];')
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


def fetch_oembed(clean_url: str) -> dict | None:
    """Fetches YouTube's lightweight oEmbed JSON payload (~50ms), or None."""
    oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url, safe='')}&format=json"
    req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=3, context=insecure_ssl_context()) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None
    return data if data.get('title') else None


def fetch_oembed_title(clean_url: str) -> str | None:
    """
    Fetches a video title through YouTube's lightweight oEmbed JSON API (~50ms).
    Returns the formatted display title, or None when unavailable.
    """
    data = fetch_oembed(clean_url)
    if not data:
        return None
    return format_display_title(data['title'], data.get('author_name', ''))


def fetch_oembed_title_pair(clean_url: str) -> tuple:
    """Returns (display_title, raw_title) from oEmbed, or (None, None)."""
    data = fetch_oembed(clean_url)
    if not data:
        return None, None
    return format_display_title(data['title'], data.get('author_name', '')), data['title']


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
