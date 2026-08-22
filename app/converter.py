import os
import re
import subprocess
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, APIC, ID3NoHeaderError
from .logger import log
from .utils import get_ffmpeg_path

import time

def convert_m4a_to_mp3_fast(source_audio: str, mp3_path: str, title: str = "", artist: str = "", is_cancelled_cb=None, volume_boost: str = "100% (Original)", quality: str = "192 kbps") -> bool:
    """
    Rock-Solid Fast Audio Transcoder.
    Strips video/subtitle streams (-vn -sn -dn) and transcodes audio to MP3 using customizable LAME bitrates.
    Supports real-time cancellation and volume amplification.
    """
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin or not os.path.exists(source_audio):
        log.error(f"Cannot start conversion. FFmpeg present: {bool(ffmpeg_bin)}, Source present: {os.path.exists(source_audio)}")
        return False

    base_no_ext = os.path.splitext(source_audio)[0]
    thumb_file = None
    for ext in ['.jpg', '.png', '.webp', '.jpeg']:
        possible_thumb = base_no_ext + ext
        if os.path.exists(possible_thumb):
            thumb_file = possible_thumb
            break

    # Extract user-selected bitrate (e.g. 320k, 256k, 192k, 128k, 96k)
    bitrate_match = re.search(r'(\d+)', quality)
    bitrate = f"{bitrate_match.group(1)}k" if bitrate_match else "192k"

    # Windows-specific process flags to eliminate console window spawn overhead
    creationflags = 0
    if os.name == 'nt':
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

    # Clean, High-Speed FFmpeg Command
    cmd = [
        ffmpeg_bin,
        "-y",
        "-loglevel", "error",
        "-threads", "0",                         # Max CPU parallelism
        "-i", source_audio,
        "-vn", "-sn", "-dn",                     # Ignore video, subtitle, and data streams
    ]

    # Apply volume filter if boost is requested
    boost_match = re.search(r'(\d+)%', volume_boost)
    if boost_match and int(boost_match.group(1)) > 100:
        vol_factor = int(boost_match.group(1)) / 100.0
        cmd.extend(["-filter:a", f"volume={vol_factor}"])

    cmd.extend([
        "-c:a", "libmp3lame",
        "-b:a", bitrate,                         # Customizable CBR Bitrate
        "-compression_level", "2",               # High quality LAME encoding
        "-ac", "2",
        "-ar", "44100",
        "-id3v2_version", "3",
        mp3_path
    ])

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=creationflags)
    while proc.poll() is None:
        if is_cancelled_cb and is_cancelled_cb():
            proc.kill()
            proc.wait()
            if os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except Exception:
                    pass
            return False
        time.sleep(0.05)

    if proc.returncode != 0:
        err = proc.stderr.read().decode('utf-8', errors='ignore')
        log.error(f"FFmpeg conversion failed for {source_audio}: {err}")
        return False

    # Ingest ID3 Tags & Cover Art instantly via Mutagen (<2ms, 0 FFmpeg video overhead)
    try:
        try:
            id3 = ID3(mp3_path)
        except ID3NoHeaderError:
            id3 = ID3()

        if title:
            id3.add(TIT2(encoding=3, text=title))
        if artist:
            id3.add(TPE1(encoding=3, text=artist))

        if thumb_file and os.path.exists(thumb_file):
            try:
                with open(thumb_file, 'rb') as img_f:
                    img_bytes = img_f.read()

                # Convert WebP/PNG -> Genuine JPEG for ID3 APIC compliance
                from PySide6.QtGui import QImage
                from PySide6.QtCore import QBuffer, QIODevice
                qimg = QImage()
                if qimg.loadFromData(img_bytes):
                    buf = QBuffer()
                    buf.open(QIODevice.WriteOnly)
                    if qimg.save(buf, "JPEG"):
                        img_bytes = buf.data().data()

                id3.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3, # Front cover
                    desc='Cover',
                    data=img_bytes
                ))
            except Exception as img_err:
                log.debug(f"Cover art embed notice: {img_err}")

        id3.save(mp3_path, v2_version=3)
    except Exception as tag_err:
        log.debug(f"ID3 tag write notice: {tag_err}")

    # Clean up temporary thumbnail image
    if thumb_file and os.path.exists(thumb_file):
        try:
            os.remove(thumb_file)
        except Exception:
            pass

    return True