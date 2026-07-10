import os
from PySide6.QtCore import QRunnable, QObject, Signal
from .utils import get_ffmpeg_path
from .logger import log

class DownloadSignals(QObject):
    progress = Signal(str, dict)  # task_id, progress_data
    finished = Signal(str)
    error = Signal(str, str)

class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, url: str, options: dict):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.options = options
        self.signals = DownloadSignals()
        self.is_cancelled = False

    def hook(self, d):
        if self.is_cancelled:
            raise Exception("CANCELLED_BY_USER")

        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
            speed = d.get('_speed_str', '0 KiB/s').replace('\x1b[0;32m', '').replace('\x1b[0m', '').strip()
            eta = d.get('_eta_str', 'Unknown').replace('\x1b[0;33m', '').replace('\x1b[0m', '').strip()
            
            data = {
                'percent': percent,
                'speed': speed,
                'eta': eta,
                'filename': d.get('filename', 'Unknown')
            }
            self.signals.progress.emit(self.task_id, data)

    def run(self):
        log.info(f"Starting download task {self.task_id} for URL: {self.url}")
        
        # 1. Immediate visual feedback
        self.signals.progress.emit(self.task_id, {
            'title': 'Extracting metadata...',
            'status_text': 'Analyzing Link...'
        })
        
        # LAZY IMPORT: Keeps application startup instant and lightweight
        import yt_dlp
        
        ffmpeg_path = get_ffmpeg_path()
        
        # Base options with network retry configurations and safety headers
        ydl_opts = {
            'outtmpl': os.path.join(self.options['download_path'], '%(title)s.%(ext)s'),
            'progress_hooks': [self.hook],
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True,
            'nocheckcertificate': True,
            'noplaylist': True,  # Force single video downloads globally
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            }
        }

        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        # Setup formats based on choices and local FFmpeg availability
        fmt = self.options.get('format', 'Best Quality')
        quality = self.options.get('quality', 'Best')
        height_limit = f"[height<={quality.replace('p', '')}]" if quality != "Best" else ""

        if not ffmpeg_path:
            # High-reliability Fallback (No FFmpeg found anywhere)
            if fmt == "MP3 Audio":
                raise RuntimeError("FFmpeg is missing! Audio cannot be converted to MP3.")
            
            log.warning("FFmpeg not found. Restricting stream requests to pre-merged files to prevent failures.")
            ydl_opts['format'] = f'best{height_limit}/best'
        else:
            # Standard adaptive format downloader (FFmpeg present)
            if fmt == "MP3 Audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            elif fmt == "MP4 Video":
                # Universal Compatibility Strategy:
                # 1. Prioritize standard H.264 (avc1) video and AAC (mp4a) audio so downloads are instant.
                # 2. If YouTube only has AV1/VP9/Opus at the requested resolution (like 1440p+),
                #    recode_video will force FFmpeg to transcode it down to standard H.264/AAC MP4.
                ydl_opts['format'] = f'bestvideo{height_limit}+bestaudio/best{height_limit}/best'
                ydl_opts['format_sort'] = ['vcodec:h264', 'acodec:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
                ydl_opts['recode_video'] = 'mp4'
            else:  # Best Quality (Will download raw AV1/VP9 inside MKV if that's the absolute best)
                ydl_opts['format'] = f'bestvideo{height_limit}+bestaudio/best{height_limit}/best'
                ydl_opts['merge_output_format'] = 'mkv'

        # Optional metadata embedding
        postprocessors = ydl_opts.get('postprocessors', [])
        if self.options.get('embed_metadata') and ffmpeg_path:
            postprocessors.append({'key': 'FFmpegMetadata'})
        if self.options.get('embed_thumbnail') and ffmpeg_path:
            ydl_opts['writethumbnail'] = True
            postprocessors.append({'key': 'EmbedThumbnail'})
        ydl_opts['postprocessors'] = postprocessors

        try:
            # 2. Extract metadata quickly using flat-playlist mode
            extract_opts = ydl_opts.copy()
            extract_opts['extract_flat'] = 'in_playlist'
            
            with yt_dlp.YoutubeDL(extract_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                title = info.get('title', 'Unknown Title')
                self.signals.progress.emit(self.task_id, {'title': title, 'status_text': 'Downloading...'})
            
            # 3. Perform actual single-video download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            
            if not self.is_cancelled:
                self.signals.finished.emit(self.task_id)

        except Exception as e:
            if "CANCELLED_BY_USER" in str(e):
                self.signals.error.emit(self.task_id, "Cancelled.")
                log.info(f"Task {self.task_id} cancelled.")
            elif "FFmpeg is missing" in str(e):
                self.signals.error.emit(self.task_id, "Failed: FFmpeg required for MP3.")
                log.error(f"Task {self.task_id} aborted: FFmpeg missing for MP3 extraction.")
            else:
                err_msg = str(e)
                log.error(f"Error in task {self.task_id}: {err_msg}")
                
                # Friendly error translation
                if "403" in err_msg or "Forbidden" in err_msg:
                    friendly_err = "Failed: YouTube blocked request. Try updating yt-dlp."
                elif "Sign in to confirm" in err_msg or "age" in err_msg:
                    friendly_err = "Failed: Video is age-restricted or private."
                elif "not available" in err_msg:
                    friendly_err = "Failed: Video is private or deleted."
                else:
                    friendly_err = f"Failed: {err_msg[:45]}..."
                    
                self.signals.error.emit(self.task_id, friendly_err)