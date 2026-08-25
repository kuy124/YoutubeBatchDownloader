import concurrent.futures
import os
import re
import subprocess
import threading  # Guards the shared in-memory title cache across worker threads
import time  # Used for cooling-off pause during automatic retries
import urllib.request
import yt_dlp
from PySide6.QtCore import QRunnable, QObject, Signal
from .utils import (
    build_audio_boost_filter,
    clean_youtube_url,
    fetch_oembed_title,
    format_display_title,
    format_elapsed_words,
    format_hms,
    get_aria2_path,
    get_ffmpeg_path,
    image_to_jpeg_bytes,
    insecure_ssl_context,
    is_youtube_url,
    resolve_uploader,
    extract_http_links,
)
from urllib.parse import parse_qs, urlparse
from .logger import log
from .converter import convert_m4a_to_mp3_fast, embed_wav_metadata

class TitlePreviewSignals(QObject):
    fetched = Signal(list)

# In-memory cache so re-pasting the same links never repeats network lookups
_TITLE_CACHE = {}
_TITLE_CACHE_LOCK = threading.Lock()
_TITLE_CACHE_LIMIT = 512


def _cached_title(clean_url: str):
    with _TITLE_CACHE_LOCK:
        return _TITLE_CACHE.get(clean_url)


def _store_title(clean_url: str, title: str):
    with _TITLE_CACHE_LOCK:
        if len(_TITLE_CACHE) >= _TITLE_CACHE_LIMIT:
            _TITLE_CACHE.clear()
        _TITLE_CACHE[clean_url] = title


class TitlePreviewWorker(QRunnable):
    def __init__(self, raw_lines: list):
        super().__init__()
        self.raw_lines = raw_lines
        self.signals = TitlePreviewSignals()

    def _fetch_single_title(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        if not is_youtube_url(line):
            return "Invalid URL"

        clean_url = clean_youtube_url(line)

        cached = _cached_title(clean_url)
        if cached:
            return cached

        # FAST PATH 1: Ultra-fast 50ms YouTube oEmbed JSON API
        oembed_title = fetch_oembed_title(clean_url)
        if oembed_title:
            _store_title(clean_url, oembed_title)
            return oembed_title

        # FAST PATH 2: Fallback to lightweight yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'socket_timeout': 4,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'check_formats': False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                if not info:
                    return "Failed to load title"
                title = info.get('title', 'Unknown Title')
                resolved = format_display_title(title, resolve_uploader(info))
                _store_title(clean_url, resolved)
                return resolved
        except Exception:
            return "Failed to load title"

    def run(self):
        if not self.raw_lines:
            self.signals.fetched.emit([])
            return

        # Fetch all link titles concurrently in parallel
        max_workers = min(12, len(self.raw_lines))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            previews = list(executor.map(self._fetch_single_title, self.raw_lines))

        self.signals.fetched.emit(previews)


class PlaylistExpandSignals(QObject):
    expanded = Signal(str, list)   # original_url, [(title, watch_url), ...]
    single = Signal(str, str)     # original_url, resolved_clean_url (not a playlist)
    error = Signal(str, str)      # original_url, error message


class PlaylistExpandWorker(QRunnable):
    """Enumerates playlist entries via flat extraction so each video can be
    queued individually with a numbered prefix in the queue table."""

    def __init__(self, url: str, task_id: str):
        super().__init__()
        self.url = url
        self.task_id = task_id
        self.is_cancelled = False
        self.signals = PlaylistExpandSignals()

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if self.is_cancelled:
            self.signals.error.emit(self.url, "Cancelled.")
            return

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': True,
            'noplaylist': False,
            'socket_timeout': 10,
            'nocheckcertificate': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if self.is_cancelled:
                self.signals.error.emit(self.url, "Cancelled.")
                return

            entries = info.get('entries')
            if not entries:
                # Not a playlist or empty — treat as a single video
                clean = clean_youtube_url(self.url)
                self.signals.single.emit(self.url, clean)
                return

            result = []
            for idx, entry in enumerate(entries):
                if self.is_cancelled:
                    self.signals.error.emit(self.url, "Cancelled.")
                    return
                title = entry.get('title') or f"Video {idx + 1}"
                watch_url = entry.get('url') or entry.get('webpage_url', '')
                if not watch_url and entry.get('id'):
                    watch_url = f"https://www.youtube.com/watch?v={entry['id']}"
                if watch_url:
                    result.append((title, watch_url))

            if result:
                self.signals.expanded.emit(self.url, result)
            else:
                self.signals.error.emit(self.url, "Failed: playlist is empty or private.")
        except Exception as e:
            if self.is_cancelled:
                self.signals.error.emit(self.url, "Cancelled.")
            else:
                self.signals.error.emit(self.url, f"Failed: {str(e)[:50]}")

class MetadataSignals(QObject):
    finished = Signal(str, dict)  # task_id, metadata_dict
    error = Signal(str, str)     # task_id, error_msg

class MetadataWorker(QRunnable):
    """Worker dedicated to pre-extracting song metadata across the entire queue prior to downloading."""
    def __init__(self, task_id: str, url: str):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.signals = MetadataSignals()

    def run(self):
        t0 = time.time()
        clean_url = clean_youtube_url(self.url)

        # FAST PATH 1: Ultra-fast 50ms YouTube oEmbed JSON API
        oembed_title = fetch_oembed_title(clean_url)
        if oembed_title:
            self.signals.finished.emit(self.task_id, {
                'title': oembed_title,
                'file_size': 0,
                'extraction_time': time.time() - t0
            })
            return

        # FAST PATH 2: Fallback to yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'socket_timeout': 5,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'check_formats': False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                extraction_time = time.time() - t0
                if info:
                    title = info.get('title', 'Unknown Title')
                    file_size = info.get('filesize') or info.get('filesize_approx') or 0
                    self.signals.finished.emit(self.task_id, {
                        'title': format_display_title(title, resolve_uploader(info)),
                        'file_size': file_size,
                        'extraction_time': extraction_time
                    })
                else:
                    self.signals.error.emit(self.task_id, "Failed to extract metadata")
        except Exception as e:
            self.signals.error.emit(self.task_id, f"Metadata Error: {str(e)[:35]}")

class DownloadSignals(QObject):
    progress = Signal(str, dict)  # task_id, progress_data
    finished = Signal(str, str, str, str)   # task_id, final_filepath, completion_msg, elapsed_str
    error = Signal(str, str)

# Audio track selector: Strictly enforces original creator track and drops AI auto-dubs
_ORIGINAL_BA = "(ba[format_note*=original]/ba[language=orig]/ba)"

# Audio-only formats: name -> (format selector, extraction codec, embeds cover art)
_AUDIO_FORMATS = {
    "MP3 Audio": ('ba[format_note*=original]/ba[language=orig]/ba', None, False),
    "M4A Audio": ('ba[format_note*=original][ext=m4a]/ba[ext=m4a]/ba[format_note*=original]/ba', 'm4a', True),
    "WAV Audio": ('ba[format_note*=original]/ba[language=orig]/ba', 'wav', False),
    "FLAC Audio": ('ba[format_note*=original]/ba[language=orig]/ba', 'flac', True),
    "AAC Audio": ('ba[format_note*=original][ext=m4a]/ba[ext=m4a]/ba[format_note*=original]/ba', 'aac', False),
    "OPUS Audio": ('ba[format_note*=original][ext=webm]/ba[ext=webm]/ba[format_note*=original]/ba', 'opus', True),
}

# Lossless codecs ignore the bitrate setting
_LOSSLESS_CODECS = {'wav', 'flac'}

# Thumbnail pipeline shared by every cover-art format
_THUMBNAIL_POSTPROCESSORS = [
    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False},
]

# Video containers: name -> (merge container, merged audio codec, format sort priority, embeds cover art)
# WEBM and AVI cannot carry attached artwork, so those skip thumbnail embedding.
_VIDEO_FORMATS = {
    "MP4 Video": ('mp4', 'aac', ['res', 'fps', 'quality', 'size', 'br'], True),
    "WEBM Video": ('webm', 'libopus', ['res', 'fps', 'quality'], False),
    "AVI Video": ('avi', 'libmp3lame', ['res', 'fps', 'quality'], False),
    "MOV Video": ('mov', 'aac', ['res', 'fps', 'quality'], True),
}
_BEST_QUALITY_VIDEO = ('mkv', 'aac', ['res', 'fps', 'quality', 'size', 'br'], True)


def build_video_format_string(max_h) -> str:
    """Builds a strict highest-resolution format string with original-audio preference."""
    if max_h:
        return f"bv*[height<={max_h}]+{_ORIGINAL_BA}/b[height<={max_h}]/bv*+{_ORIGINAL_BA}/b"
    return f"bv*+{_ORIGINAL_BA}/bv*+ba/b"


def build_audio_postprocessor_args(boost_filter) -> dict:
    """Postprocessor arguments applying the boost/limit filter during audio extraction."""
    if boost_filter:
        return {'extractaudio': ['-filter:a', boost_filter]}
    return {}


def build_merger_args(audio_codec: str, audio_bitrate_str: str, boost_filter) -> list:
    """FFmpeg merger arguments keeping video untouched while normalizing the audio codec."""
    merger_args = ['-c:v', 'copy', '-c:a', audio_codec, '-b:a', audio_bitrate_str]
    if boost_filter:
        merger_args.extend(['-filter:a', boost_filter])
    return merger_args


def build_format_options(fmt: str, video_format: str, audio_bitrate_num, audio_bitrate_str: str,
                         boost_filter) -> dict:
    """Declarative yt-dlp option overrides for the selected output format."""
    if fmt in _AUDIO_FORMATS:
        selector, codec, with_thumb = _AUDIO_FORMATS[fmt]
        opts = {'writethumbnail': with_thumb, 'format': selector}

        if codec is None:
            # Raw best-audio stream; conversion is handled afterwards by converter.py
            opts['postprocessors'] = []
        else:
            extract_pp = {'key': 'FFmpegExtractAudio', 'preferredcodec': codec}
            if codec not in _LOSSLESS_CODECS:
                extract_pp['preferredquality'] = audio_bitrate_num
            opts['postprocessors'] = [
                extract_pp,
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                *( _THUMBNAIL_POSTPROCESSORS if with_thumb else [] )
            ]
        pp_args = build_audio_postprocessor_args(boost_filter)
        if pp_args:
            opts['postprocessor_args'] = pp_args
        return opts

    container, audio_codec, format_sort, with_thumb = _VIDEO_FORMATS.get(fmt, _BEST_QUALITY_VIDEO)
    opts = {
        'format': video_format,
        'format_sort': list(format_sort),
        'format_sort_force': True,
        'merge_output_format': container,
    }
    postprocessors = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
    if with_thumb:
        # Embeds cover art so Explorer tiles and media players display artwork
        opts['writethumbnail'] = True
        postprocessors += _THUMBNAIL_POSTPROCESSORS
    opts['postprocessors'] = postprocessors

    pp_args = {'merger': build_merger_args(audio_codec, audio_bitrate_str, boost_filter)}
    if fmt == "AVI Video" and boost_filter:
        pp_args['videoconvertor'] = ['-filter:a', boost_filter]
    opts['postprocessor_args'] = pp_args
    return opts


def extract_media_tags(info_dict: dict) -> tuple:
    """Returns (title, artist), preferring dedicated music artist metadata fields."""
    title = info_dict.get('title', '') or ''
    return title, resolve_uploader(info_dict)


class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, url: str, options: dict, pre_data: dict = None):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.options = options
        self.pre_data = pre_data or {}
        self.signals = DownloadSignals()
        self.is_cancelled = False
        self.current_process = None
        self.final_filename = ""
        self.extraction_time = self.pre_data.get('extraction_time', 0.0)
        self.extraction_start_time = None
        self.download_start_time = None
        self.queued_time = self.options.get('queued_time') or time.time()
        self.speed_history = []  # Rolling 15-sample window for smooth Mbps & steady ETA

    def cancel(self):
        """Triggers cancellation and immediately kills any active conversion/transcoding process."""
        self.is_cancelled = True
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.kill()
            except Exception:
                pass

    def post_hook(self, d):
        if self.is_cancelled:
            raise Exception("CANCELLED_BY_USER")

        status = d.get('status')
        pp_name = d.get('postprocessor', '')

        if status == 'started':
            if 'ExtractAudio' in pp_name or 'Audio' in pp_name:
                status_text = f"Extracting {self.options.get('format', 'Audio')}..."
            elif 'EmbedThumbnail' in pp_name or 'Thumb' in pp_name:
                status_text = "Embedding Album Art..."
            elif 'Merger' in pp_name or 'Video' in pp_name:
                status_text = "Merging Streams..."
            elif 'Metadata' in pp_name:
                status_text = "Embedding Tags..."
            else:
                status_text = "Extracting Local File..."

            self.signals.progress.emit(self.task_id, {
                'status_text': status_text,
                'is_postprocessing': True,
                'speed': 'Processing...',
                'eta': 'Almost done'
            })
        elif status == 'finished':
            self.signals.progress.emit(self.task_id, {
                'status_text': "Finalizing File...",
                'is_postprocessing': True,
                'speed': '-',
                'eta': '00:00'
            })

    def hook(self, d):
        if self.is_cancelled:
            raise Exception("CANCELLED_BY_USER")

        if d['status'] == 'downloading':
            now = time.time()
            fresh_extraction_sample = False
            if self.download_start_time is None:
                self.download_start_time = now
                # The first download callback fires right after URL/stream extraction
                # finished, so the elapsed wall time is the true extraction duration
                self.extraction_time = max(0.0, now - (self.extraction_start_time or now))
                fresh_extraction_sample = True

            self.final_filename = d.get('filename', '')
            percent = d.get('_percent_str', '0%').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
            
            # Smooth Mbps & steady ETA calculation via 15-sample moving average
            instant_speed = d.get('speed', 0) or 0
            if instant_speed > 0:
                self.speed_history.append(instant_speed)
                if len(self.speed_history) > 15:
                    self.speed_history.pop(0)

            if self.speed_history:
                smooth_speed = sum(self.speed_history) / len(self.speed_history)
            else:
                elapsed = max(0.1, now - self.download_start_time)
                smooth_speed = d.get('downloaded_bytes', 0) / elapsed

            downloaded_b = d.get('downloaded_bytes', 0)
            total_b = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            remaining_b = max(0, total_b - downloaded_b)

            if smooth_speed > 0 and remaining_b > 0:
                raw_eta = remaining_b / smooth_speed
                total_task_eta_sec = int(raw_eta + self.extraction_time)
                formatted_eta = format_hms(total_task_eta_sec)
            else:
                formatted_eta = d.get('_eta_str', 'Unknown').replace('\x1b[0;33m', '').replace('\x1b[0m', '').strip()
                total_task_eta_sec = None

            # Format smooth speed into MB/s and Mbps
            mb_s = smooth_speed / (1024 * 1024)
            mbps = (smooth_speed * 8) / (1024 * 1024)
            if mb_s >= 1.0:
                formatted_speed = f"{mb_s:.2f} MB/s ({mbps:.1f} Mbps)"
            else:
                formatted_speed = f"{smooth_speed / 1024:.1f} KB/s ({mbps:.2f} Mbps)"

            info_dict = d.get('info_dict', {}) or {}
            title = info_dict.get('title')
            uploader = resolve_uploader(info_dict)

            data = {
                'percent': percent,
                'speed': formatted_speed,
                'speed_bytes': smooth_speed,
                'downloaded_bytes': downloaded_b,
                'total_bytes': total_b,
                'eta': formatted_eta,
                'eta_seconds': total_task_eta_sec,
                'filename': d.get('filename', 'Unknown')
            }
            if title:
                data['title'] = format_display_title(title, uploader)
            if fresh_extraction_sample:
                data['extraction_time'] = round(self.extraction_time, 3)

            self.signals.progress.emit(self.task_id, data)

    def cleanup_partial_files(self, filepath: str):
        """Safely removes all incomplete, converted, thumbnail, and media files when a task is cancelled."""
        download_dir = self.options.get('download_path') or (os.path.dirname(filepath) if filepath else "")
        title = self.pre_data.get('title') or ""
        
        target_bases = []
        if filepath:
            b = os.path.splitext(os.path.basename(filepath))[0]
            if b and len(b) >= 2:
                target_bases.append(b)
        if title and len(title) >= 2:
            clean_t = re.sub(r'[\\/:*?"<>|]', '_', title)
            if clean_t not in target_bases:
                target_bases.append(clean_t)

        if not download_dir or not os.path.exists(download_dir) or not target_bases:
            return

        try:
            for f in os.listdir(download_dir):
                full_path = os.path.join(download_dir, f)
                if not os.path.isfile(full_path):
                    continue
                    
                for base in target_bases:
                    if f.startswith(base):
                        try:
                            os.remove(full_path)
                            log.info(f"Cleanup: Removed cancelled task file/residue: {full_path}")
                        except Exception as ex:
                            log.error(f"Failed removing residue {full_path}: {ex}")
                        break
        except Exception as ex:
            log.error(f"Error during file cleanup: {ex}")

    def download_thumbnail(self, info_dict: dict, base_path: str):
        """Downloads the best thumbnail as a genuine JPEG next to the output file."""
        thumb_url = info_dict.get('thumbnail')
        if not thumb_url and info_dict.get('thumbnails'):
            thumb_url = info_dict['thumbnails'][-1].get('url')
        if not thumb_url or self.is_cancelled:
            return None

        try:
            thumb_path = base_path + '.jpg'
            req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=2, context=insecure_ssl_context()) as resp:
                raw_bytes = resp.read()

            # Re-encode WebP/PNG payloads into a standard JPEG
            with open(thumb_path, 'wb') as f:
                f.write(image_to_jpeg_bytes(raw_bytes))
            return thumb_path
        except Exception as ex:
            log.debug(f"Thumbnail download notice: {ex}")
            return None

    def _convert_to_mp3(self, ydl, info_dict: dict, boost_str: str, quality: str) -> bool:
        """MP3 conversion pass. Returns False when run() must stop (cancelled or failed)."""
        if self.is_cancelled:
            self.cleanup_partial_files(self.final_filename)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        downloaded_file = ydl.prepare_filename(info_dict)
        base_path = os.path.splitext(downloaded_file)[0]
        mp3_path = base_path + '.mp3'

        # Locate downloaded audio stream file (.m4a, .webm, etc.)
        source_file = downloaded_file
        if not os.path.exists(source_file):
            for ext in ['.m4a', '.webm', '.opus', '.mp4']:
                if os.path.exists(base_path + ext):
                    source_file = base_path + ext
                    break

        if not (os.path.exists(source_file) and source_file != mp3_path):
            return True

        self.signals.progress.emit(self.task_id, {
            'status_text': 'Converting...',
            'is_postprocessing': True
        })

        # Universal Thumbnail Fetcher for the ID3 cover art pass
        self.download_thumbnail(info_dict, base_path)

        if self.is_cancelled:
            self.cleanup_partial_files(source_file)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        title, artist = extract_media_tags(info_dict)

        success = convert_m4a_to_mp3_fast(
            source_file, mp3_path, title=title, artist=artist,
            is_cancelled_cb=lambda: self.is_cancelled,
            volume_boost=boost_str,
            quality=quality
        )

        if self.is_cancelled:
            self.cleanup_partial_files(mp3_path)
            self.cleanup_partial_files(source_file)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        if success and os.path.exists(mp3_path):
            try:
                os.remove(source_file)
                log.info(f"Conversion finished: {mp3_path}")
            except Exception as ex:
                log.warning(f"Could not remove source file {source_file}: {ex}")
        else:
            if not self.is_cancelled:
                self.signals.error.emit(self.task_id, "Failed: Audio conversion failed.")
            else:
                self.cleanup_partial_files(mp3_path)
                self.cleanup_partial_files(source_file)
                self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        return True

    def _remux_aac(self, ffmpeg_path: str, ydl, info_dict: dict,
                   audio_bitrate_str: str, boost_filter) -> bool:
        """Remuxes the M4A container to raw .aac with ID3v2 metadata. Returns False to abort run()."""
        if self.is_cancelled:
            self.cleanup_partial_files(self.final_filename)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        downloaded_file = ydl.prepare_filename(info_dict)
        base_path = os.path.splitext(downloaded_file)[0]
        aac_path = base_path + '.aac'
        if not (os.path.exists(downloaded_file) and downloaded_file != aac_path):
            return True

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if os.name == 'nt' else 0
        aac_cmd = [
            ffmpeg_path, '-y', '-threads', '0',
            '-i', downloaded_file,
            '-vn'
        ]
        aac_cmd.extend(['-c:a', 'aac', '-b:a', audio_bitrate_str])
        if boost_filter:
            aac_cmd.extend(['-filter:a', boost_filter])
        aac_cmd.extend([
            '-map_metadata', '0',
            '-write_id3v2', '1',
            aac_path
        ])
        proc = subprocess.Popen(aac_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)

        self.current_process = proc
        while proc.poll() is None:
            if self.is_cancelled:
                proc.kill()
                proc.wait()
                self.cleanup_partial_files(aac_path)
                self.cleanup_partial_files(downloaded_file)
                self.signals.error.emit(self.task_id, "Cancelled.")
                return False
            time.sleep(0.05)
        self.current_process = None

        if self.is_cancelled:
            self.cleanup_partial_files(aac_path)
            self.cleanup_partial_files(downloaded_file)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        if os.path.exists(aac_path):
            try:
                os.remove(downloaded_file)
            except Exception:
                pass
        return True

    def _embed_wav_art(self, ydl, info_dict: dict) -> bool:
        """Embeds title/artist/cover art into the WAV ID3 chunk via mutagen; yt-dlp cannot
        attach thumbnails to .wav. Returns False to abort run()."""
        if self.is_cancelled:
            self.cleanup_partial_files(self.final_filename)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        wav_file = ydl.prepare_filename(info_dict)
        if wav_file and not wav_file.endswith('.wav'):
            wav_file = os.path.splitext(wav_file)[0] + '.wav'

        if not os.path.exists(wav_file):
            return True

        self.signals.progress.emit(self.task_id, {
            'status_text': 'Embedding Album Art...',
            'is_postprocessing': True
        })

        base_path = os.path.splitext(wav_file)[0]
        thumb_path = self.download_thumbnail(info_dict, base_path)

        if self.is_cancelled:
            self.cleanup_partial_files(thumb_path)
            self.cleanup_partial_files(self.final_filename)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return False

        title, artist = extract_media_tags(info_dict)
        embed_wav_metadata(wav_file, thumb_path=thumb_path,
                           title=title, artist=artist)

        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        return True

    def _resolve_final_path(self, ydl, info_dict: dict, fmt: str) -> str:
        """Calculates the true destination file path for instant GUI playback."""
        final_path = ""
        if info_dict:
            prepared_path = ydl.prepare_filename(info_dict)
            ext_map = {
                "MP3 Audio": ".mp3", "M4A Audio": ".m4a", "WAV Audio": ".wav",
                "FLAC Audio": ".flac", "AAC Audio": ".aac", "OPUS Audio": ".opus",
                "MP4 Video": ".mp4", "WEBM Video": ".webm", "AVI Video": ".avi", "MOV Video": ".mov"
            }
            if fmt in ext_map:
                final_path = os.path.splitext(prepared_path)[0] + ext_map[fmt]
            else:
                final_path = prepared_path

        if not final_path or not os.path.exists(final_path):
            final_path = self.final_filename
            if final_path and fmt == "MP3 Audio" and not final_path.endswith('.mp3'):
                final_path = os.path.splitext(final_path)[0] + '.mp3'
        if not final_path:
            final_path = self.options['download_path']
        return final_path

    def run(self):
        # Fast-exit path for tasks cancelled while still queued in the capped pool
        if self.is_cancelled:
            log.info(f"Task {self.task_id} cancelled before starting; skipping.")
            self.cleanup_partial_files(self.final_filename)
            self.signals.error.emit(self.task_id, "Cancelled.")
            return

        log.info(f"Starting stream download task {self.task_id} for URL: {self.url}")

        # Timestamp anchor for measuring the real URL/stream extraction duration
        self.extraction_start_time = time.time()

        # Pre-extracted metadata exists; immediately notify UI and proceed to stream download
        initial_title = self.pre_data.get('title', 'Preparing stream...')
        self.signals.progress.emit(self.task_id, {
            'title': initial_title,
            'status_text': 'Downloading'
        })

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        ydl_opts = {
            'outtmpl': os.path.join(self.options['download_path'], '%(title)s.%(ext)s'),
            'parse_metadata': [
                '%(uploader,channel,creator,artist)s:%(artist)s',
                '%(uploader,channel,creator,artist)s:%(album_artist)s',
                '%(uploader,channel,creator)s:%(composer)s',
                '%(title)s:%(album)s'
            ],
            'replace_in_metadata': [
                ('title', r'^(.+?)\s*-\s*\1\s*-\s*', r'\1 - ')
            ],
            'progress_hooks': [self.hook],
            'postprocessor_hooks': [self.post_hook],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'noplaylist': True,
            'cachedir': False,
            'concurrent_fragment_downloads': 16,  # Parallel fragments for HLS/DASH streams
            'throttled_rate': 102400,           # Drops & restarts connection if YouTube throttles speed below 100KB/s
            'retries': 15,
            'fragment_retries': 15,
            'file_access_retries': 5,
            'socket_timeout': 15,               # Fast timeout recovery so it never hangs for 30s
            'retry_sleep_functions': {
                'http': lambda n: 0.5,          # Fast recovery without sleeping
                'fragment': lambda n: 0.5
            },
        }

        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        max_speed_mb = int(self.options.get('max_speed_mb', 0))
        if max_speed_mb > 0:
            ydl_opts['ratelimit'] = max_speed_mb * 1024 * 1024

        # Opt-in multi-connection engine (settings.json: "use_aria2": true).
        # aria2c splits single files into 16 ranged connections, which saturates
        # very fast lines; benchmarked slower on standard lines so it stays off
        # by default. Note: live progress ticks pause while it runs.
        if self.options.get('use_aria2'):
            aria2_path = get_aria2_path()
            if aria2_path:
                ydl_opts['external_downloader'] = aria2_path
            else:
                log.warning(
                    "use_aria2 is enabled in settings but no aria2c.exe was found "
                    "(tools/aria2c.exe or PATH). Falling back to the native "
                    "downloader. Run install.bat to fetch it."
                )

        fmt = self.options.get('format', 'Best Quality (MKV)')
        quality = self.options.get('quality', 'Best')
        boost_str = self.options.get('audio_boost', '100% (Original)')
        boost_filter = build_audio_boost_filter(boost_str)

        # Numeric parser for video resolution (height) & audio bitrate
        num_match = re.search(r'(\d+)', quality)
        parsed_num = num_match.group(1) if num_match else None

        max_h = parsed_num if (parsed_num and "Audio" not in fmt and "Best" not in quality) else None
        audio_bitrate_num = parsed_num if (parsed_num and "Audio" in fmt) else "192"
        audio_bitrate_str = f"{audio_bitrate_num}k"

        video_format = build_video_format_string(max_h)

        if not ffmpeg_path:
            self.signals.error.emit(self.task_id, "Failed: FFmpeg binary missing in tools/. Please run install.bat.")
            return

        ydl_opts.update(build_format_options(
            fmt, video_format, audio_bitrate_num, audio_bitrate_str, boost_filter
        ))

        # --- Automatic Background Retry Loop ---
        max_auto_retries = 3
        for attempt in range(max_auto_retries + 1):
            if self.is_cancelled:
                self.cleanup_partial_files(self.final_filename)
                self.signals.error.emit(self.task_id, "Cancelled.")
                return
                
            try:
                # Single-pass download execution
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(self.url, download=True)

                # Format-specific post-processing passes; each returns False to abort
                if fmt == "MP3 Audio" and info_dict:
                    if not self._convert_to_mp3(ydl, info_dict, boost_str, quality):
                        return

                if fmt == "AAC Audio" and ffmpeg_path and info_dict:
                    if not self._remux_aac(ffmpeg_path, ydl, info_dict,
                                           audio_bitrate_str, boost_filter):
                        return

                if fmt == "WAV Audio" and info_dict:
                    if not self._embed_wav_art(ydl, info_dict):
                        return

                if not self.is_cancelled:
                    final_path = self._resolve_final_path(ydl, info_dict, fmt)

                    elapsed_sec = int(time.time() - self.queued_time)
                    elapsed_str = format_elapsed_words(elapsed_sec)
                    
                    completion_msg = f"Your download completed in {elapsed_str}"
                    self.signals.finished.emit(self.task_id, final_path, completion_msg, elapsed_str)
                return

            except Exception as e:
                # If user manually triggers Cancel, break out of loop immediately and clean up partial files
                if "CANCELLED_BY_USER" in str(e) or self.is_cancelled:
                    log.info(f"Task {self.task_id} was cancelled by user.")
                    self.cleanup_partial_files(self.final_filename)
                    self.signals.error.emit(self.task_id, "Cancelled.")
                    return
                
                # If we haven't exhausted our auto-retry threshold, perform backoff pause and try again
                if attempt < max_auto_retries:
                    log.warning(f"Task {self.task_id} failed on attempt {attempt + 1}. Retrying automatically...")
                    self.signals.progress.emit(self.task_id, {
                        'status_text': f'Retrying ({attempt + 1}/3)...'
                    })
                    time.sleep(2)  # Safe backoff wait
                else:
                    err_msg = str(e)
                    log.error(f"Task {self.task_id} exhausted all auto-retries. Final Error: {err_msg}")
                    
                    if "403" in err_msg or "Forbidden" in err_msg:
                        friendly_err = "Failed: YouTube blocked request. Try updating yt-dlp."
                    elif "Sign in to confirm" in err_msg or "age" in err_msg:
                        friendly_err = "Failed: Video is age-restricted or private."
                    elif "not available" in err_msg:
                        friendly_err = "Failed: Video is private or deleted."
                    else:
                        friendly_err = f"Failed: {err_msg[:45]}..."
                        
                    self.signals.error.emit(self.task_id, friendly_err)
                    return