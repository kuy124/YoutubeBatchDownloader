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

    def _fetch_single_title(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        if "youtube.com/" not in line and "youtu.be/" not in line:
            return "Invalid URL"

        clean_url = self._clean_url(line)

        # FAST PATH 1: Ultra-fast 50ms YouTube oEmbed JSON API
        import urllib.request
        import urllib.parse
        import json
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url, safe='')}&format=json"
            req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    title = data.get('title', '')
                    uploader = data.get('author_name', '')
                    if title:
                        if uploader and uploader.lower() not in title.lower():
                            return f"{uploader} - {title}"
                        return title
        except Exception:
            pass

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
                uploader = info.get('artist') or info.get('uploader') or info.get('creator') or info.get('channel')
                if uploader and uploader.lower() not in title.lower():
                    return f"{uploader} - {title}"
                return title
        except Exception:
            return "Failed to load title"

    def run(self):
        if not self.raw_lines:
            self.signals.fetched.emit([])
            return

        import concurrent.futures
        # Fetch all link titles concurrently in parallel
        max_workers = min(12, len(self.raw_lines))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            previews = list(executor.map(self._fetch_single_title, self.raw_lines))

        self.signals.fetched.emit(previews)

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

    def _clean_url(self, url: str) -> str:
        if "youtube.com/watch" in url and "v=" in url:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return f"https://www.youtube.com/watch?v={qs['v'][0]}"
        return url

    def run(self):
        t0 = time.time()
        clean_url = self._clean_url(self.url)

        # FAST PATH 1: Ultra-fast 50ms YouTube oEmbed JSON API
        import urllib.request
        import urllib.parse
        import json
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url, safe='')}&format=json"
            req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    title = data.get('title', '')
                    uploader = data.get('author_name', '')
                    if title:
                        display_title = f"{uploader} - {title}" if uploader and uploader.lower() not in title.lower() else title
                        extraction_time = time.time() - t0
                        self.signals.finished.emit(self.task_id, {
                            'title': display_title,
                            'file_size': 0,
                            'extraction_time': extraction_time
                        })
                        return
        except Exception:
            pass

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
                    uploader = info.get('artist') or info.get('uploader') or info.get('creator') or info.get('channel')
                    display_title = f"{uploader} - {title}" if uploader and uploader.lower() not in title.lower() else title
                    file_size = info.get('filesize') or info.get('filesize_approx') or 0
                    self.signals.finished.emit(self.task_id, {
                        'title': display_title,
                        'file_size': file_size,
                        'extraction_time': extraction_time
                    })
                else:
                    self.signals.error.emit(self.task_id, "Failed to extract metadata")
        except Exception as e:
            self.signals.error.emit(self.task_id, f"Metadata Error: {str(e)[:35]}")

class DownloadSignals(QObject):
    progress = Signal(str, dict)  # task_id, progress_data
    finished = Signal(str, str)   # task_id, final_filepath (emits file path to open directly)
    error = Signal(str, str)

class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, url: str, options: dict, pre_data: dict = None):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.options = options
        self.pre_data = pre_data or {}
        self.signals = DownloadSignals()
        self.is_cancelled = False
        self.final_filename = ""
        self.extraction_time = self.pre_data.get('extraction_time', 0.0)
        self.download_start_time = None
        self.speed_history = []  # Rolling 15-sample window for smooth Mbps & steady ETA

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
            if self.download_start_time is None:
                self.download_start_time = now

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
                mins, secs = divmod(total_task_eta_sec, 60)
                hours, mins = divmod(mins, 60)
                formatted_eta = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
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
            uploader = info_dict.get('artist') or info_dict.get('uploader') or info_dict.get('creator') or info_dict.get('channel')

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
        log.info(f"Starting stream download task {self.task_id} for URL: {self.url}")
        
        # Pre-extracted metadata exists; immediately notify UI and proceed to stream download
        initial_title = self.pre_data.get('title', 'Preparing stream...')
        self.signals.progress.emit(self.task_id, {
            'title': initial_title,
            'status_text': 'Downloading'
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
                'postprocessor_hooks': [self.post_hook],
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'noplaylist': True,  # Globally force single video downloads
                'retries': 10,
                'fragment_retries': 10,
                'socket_timeout': 30,
                
                # SPEED OPTIMIZATIONS: Skip extra manifests, use 10MB chunk buffer
                'youtube_include_dash_manifest': False,
                'youtube_include_hls_manifest': False,
                'http_chunk_size': 10485760,  # 10MB chunk size for higher bandwidth utilization
                
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
            
            # WINDOWS COMPATIBLE ID3v2.3 TAGS & NATIVE FFmpeg 1:1 SQUARE COVER ART CROPPING
            ydl_opts['postprocessor_args'] = {
                'ffmpeg': ['-threads', '0', '-preset', 'ultrafast', '-id3v2_version', '3'],
                'FFmpegMerger': ['-c:v', 'copy', '-c:a', 'copy', '-movflags', '+faststart'],
                'FFmpegExtractAudio': ['-threads', '0', '-compression_level', '0', '-q:a', '2', '-ac', '2', '-id3v2_version', '3'],
                'ExtractAudio': ['-threads', '0', '-compression_level', '0', '-q:a', '2', '-ac', '2', '-id3v2_version', '3'],
                'FFmpegThumbnailsConvertor': ['-vf', 'crop=ih:ih'],  # Natively crops thumbnail to 1:1 square
                'EmbedThumbnail': ['-id3v2_version', '3'],
                'FFmpegVideoConvertor': ['-preset', 'ultrafast']
            }

        # Setup formats based on choices and local FFmpeg availability
        fmt = self.options.get('format', 'Best Quality (MKV)')
        quality = self.options.get('quality', 'Best')
        q_limit = f"[height<={quality.replace('p', '')}]" if quality != "Best" else ""

        if not ffmpeg_path:
            if "Audio" in fmt:
                self.signals.error.emit(self.task_id, f"Failed: FFmpeg required for {fmt}.")
                return
            log.warning("FFmpeg not found. Restricting stream requests to pre-merged files.")
            ydl_opts['format'] = f'best{q_limit}/best'
        else:
            if "Audio" in fmt:
                # Enable cover art thumbnail downloading & embedding for all audio files
                ydl_opts['writethumbnail'] = True

            if fmt == "MP3 Audio":
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "M4A Audio":
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "WAV Audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "FLAC Audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "AAC Audio":
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'aac'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "OPUS Audio":
                ydl_opts['format'] = 'bestaudio[ext=webm]/bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'opus'},
                    {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            elif fmt == "MP4 Video":
                ydl_opts['format'] = f'bestvideo{q_limit}[ext=mp4]+bestaudio[ext=m4a]/bestvideo{q_limit}+bestaudio/best'
                ydl_opts['format_sort'] = ['vcodec:h264', 'acodec:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
            elif fmt == "WEBM Video":
                ydl_opts['format'] = f'bestvideo{q_limit}[ext=webm]+bestaudio[ext=webm]/bestvideo{q_limit}+bestaudio/best'
                ydl_opts['merge_output_format'] = 'webm'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
            elif fmt == "AVI Video":
                ydl_opts['format'] = f'bestvideo{q_limit}+bestaudio/best'
                ydl_opts['merge_output_format'] = 'avi'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
            elif fmt == "MOV Video":
                ydl_opts['format'] = f'bestvideo{q_limit}+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mov'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
            else:  # Best Quality (MKV)
                ydl_opts['format'] = f'bestvideo{q_limit}+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mkv'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]

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