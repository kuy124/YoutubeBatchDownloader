import os
import time  # Used for cooling-off pause during automatic retries
import yt_dlp
from PySide6.QtCore import QRunnable, QObject, Signal
from .utils import get_ffmpeg_path
from .logger import log

class TitlePreviewSignals(QObject):
    fetched = Signal(list)

from urllib.parse import urlparse, parse_qs

class TitlePreviewWorker(QRunnable):
    def __init__(self, raw_lines: list):
        super().__init__()
        self.raw_lines = raw_lines
        self.signals = TitlePreviewSignals()

    def _clean_url(self, url: str) -> str:
        """Strips mix/playlist parameters to ensure single video metadata is fetched."""
        if "youtube.com/watch" in url and "v=" in url:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return f"https://www.youtube.com/watch?v={qs['v'][0]}"
        return url

    def run(self):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'socket_timeout': 10,
        }
        previews = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for raw_line in self.raw_lines:
                line = raw_line.strip()
                
                # Maintain 1-to-1 line matching for empty lines
                if not line:
                    previews.append("")
                    continue

                if "youtube.com/" not in line and "youtu.be/" not in line:
                    previews.append("Invalid URL")
                    continue

                clean_url = self._clean_url(line)
                try:
                    info = ydl.extract_info(clean_url, download=False)
                    title = info.get('title', 'Unknown Title')
                    uploader = info.get('artist') or info.get('uploader') or info.get('creator') or info.get('channel')
                    if uploader and uploader.lower() not in title.lower():
                        display_title = f"{uploader} - {title}"
                    else:
                        display_title = title
                    previews.append(display_title)
                except Exception:
                    previews.append("Failed to load title")
                    
        self.signals.fetched.emit(previews)

class DownloadSignals(QObject):
    progress = Signal(str, dict)  # task_id, progress_data
    finished = Signal(str, str)   # task_id, final_filepath (emits file path to open directly)
    error = Signal(str, str)

class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, url: str, options: dict):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.options = options
        self.signals = DownloadSignals()
        self.is_cancelled = False
        self.final_filename = ""  # Captures file destination in real-time

    def hook(self, d):
        if self.is_cancelled:
            raise Exception("CANCELLED_BY_USER")

        if d['status'] == 'downloading':
            self.final_filename = d.get('filename', '')
            percent = d.get('_percent_str', '0%').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
            speed = d.get('_speed_str', '0 KiB/s').replace('\x1b[0;32m', '').replace('\x1b[0m', '').strip()
            eta = d.get('_eta_str', 'Unknown').replace('\x1b[0;33m', '').replace('\x1b[0m', '').strip()
            
            # Extract video title and author/artist dynamically on-the-fly from active stream
            info_dict = d.get('info_dict', {}) or {}
            title = info_dict.get('title')
            uploader = info_dict.get('artist') or info_dict.get('uploader') or info_dict.get('creator') or info_dict.get('channel')
            
            data = {
                'percent': percent,
                'speed': speed,
                'speed_bytes': d.get('speed', 0),
                'downloaded_bytes': d.get('downloaded_bytes', 0),
                'total_bytes': d.get('total_bytes') or d.get('total_bytes_estimate', 0),
                'eta': eta,
                'eta_seconds': d.get('eta'),
                'filename': d.get('filename', 'Unknown')
            }
            if title:
                # Standard Windows Native Music Display: Author - Title
                if uploader and uploader.lower() not in title.lower():
                    data['title'] = f"{uploader} - {title}"
                else:
                    data['title'] = title
                
            self.signals.progress.emit(self.task_id, data)

    def cleanup_partial_files(self, filepath: str):
        """Safely removes all incomplete, .part, and fragment files generated during download."""
        if not filepath:
            return
        try:
            # 1. Delete standard .part file
            part_file = filepath + ".part"
            if os.path.exists(part_file):
                os.remove(part_file)
                log.info(f"Cleanup: Deleted partial file: {part_file}")
            
            # 2. Delete the main file path itself if partially written
            if os.path.exists(filepath):
                os.remove(filepath)
                log.info(f"Cleanup: Deleted incomplete file: {filepath}")
            
            # 3. Clean up format-specific fragment files (e.g. video.f137.mp4.part, video.f140.m4a.part)
            dir_name = os.path.dirname(filepath)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            
            # Safety guard: avoid scanning if base name is abnormally short
            if not base_name or len(base_name) < 2:
                return
                
            if os.path.exists(dir_name):
                for f in os.listdir(dir_name):
                    if f.startswith(base_name) and (f.endswith('.part') or f.endswith('.temp') or f.endswith('.ytdl')):
                        full_path = os.path.join(dir_name, f)
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            log.info(f"Cleanup: Deleted partial fragment file: {full_path}")
        except Exception as ex:
            log.error(f"Error during partial file cleanup for {filepath}: {ex}")

    def run(self):
        log.info(f"Starting download task {self.task_id} for URL: {self.url}")
        
        # 1. Immediate visual feedback
        self.signals.progress.emit(self.task_id, {
            'title': 'Extracting metadata...',
            'status_text': 'Analyzing Link...'
        })
        
        ffmpeg_path = get_ffmpeg_path()
        
        # Output template formatted for Windows Native Music/Media saving format with duplication prevention
        ydl_opts = {
            'outtmpl': os.path.join(self.options['download_path'], '%(title)s.%(ext)s'),
            'parse_metadata': [
                'title:^(?P<title>[^-]+)$:%(uploader,artist)s - %(title)s'
            ],
            'replace_in_metadata': [
                ('title', r'^(.+?)\s*-\s*\1\s*-\s*', r'\1 - ')
            ],
            'progress_hooks': [self.hook],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'noplaylist': True,  # Globally force single video downloads
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            
            # Embed native metadata (Artist, Title, Album) for Windows File Explorer & Media Player
            'addmetadata': True,
            
            # PERFORMANCE ENHANCEMENT: Downloads up to 16 stream fragments concurrently (parallel downloading)
            'concurrent_fragment_downloads': 16,
            
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            }
        }

        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # PERFORMANCE ENHANCEMENT: Utilize 100% of available CPU cores (-threads 0)
            ydl_opts['postprocessor_args'] = {
                'ffmpeg': ['-threads', '0'],
                'ffmpegextractaudio': ['-threads', '0'],
                'ffmpegvideoconvertor': ['-threads', '0', '-preset', 'ultrafast']
            }

        # Setup formats based on choices and local FFmpeg availability
        fmt = self.options.get('format', 'Best Quality')
        quality = self.options.get('quality', 'Best')
        height_limit = f"[height<={quality.replace('p', '')}]" if quality != "Best" else ""

        if not ffmpeg_path:
            # High-reliability Fallback (No FFmpeg found anywhere)
            if fmt == "MP3 Audio":
                self.signals.error.emit(self.task_id, "Failed: FFmpeg required for MP3.")
                return
            
            log.warning("FFmpeg not found. Restricting stream requests to pre-merged files to prevent failures.")
            ydl_opts['format'] = f'best{height_limit}/best'
        else:
            # Standard adaptive format downloader with embedded metadata
            if fmt == "MP3 Audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]
            elif fmt == "MP4 Video":
                ydl_opts['format'] = f'bestvideo{height_limit}+bestaudio/best{height_limit}/best'
                ydl_opts['format_sort'] = ['vcodec:h264', 'acodec:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
                ydl_opts['recode_video'] = 'mp4'
                ydl_opts['postprocessors'] = [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]
            else:  # Best Quality
                ydl_opts['format'] = f'bestvideo{height_limit}+bestaudio/best{height_limit}/best'
                ydl_opts['merge_output_format'] = 'mkv'
                ydl_opts['postprocessors'] = [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]

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
                
                # Calculate true destination file path for instant GUI playback
                if not self.is_cancelled:
                    final_path = ""
                    if info_dict:
                        prepared_path = ydl.prepare_filename(info_dict)
                        if fmt == "MP3 Audio":
                            final_path = os.path.splitext(prepared_path)[0] + '.mp3'
                        elif fmt == "MP4 Video":
                            final_path = os.path.splitext(prepared_path)[0] + '.mp4'
                        else:
                            final_path = prepared_path
                            
                    if not final_path or not os.path.exists(final_path):
                        final_path = self.final_filename
                        if final_path and fmt == "MP3 Audio" and not final_path.endswith('.mp3'):
                            final_path = os.path.splitext(final_path)[0] + '.mp3'
                    if not final_path:
                        final_path = self.options['download_path']
                        
                    self.signals.finished.emit(self.task_id, final_path)
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
                    # Final crash out of automated retry block. Forward final errors to GUI controller.
                    err_msg = str(e)
                    log.error(f"Task {self.task_id} exhausted all auto-retries. Final Error: {err_msg}")
                    
                    # Friendly error translation mapping
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