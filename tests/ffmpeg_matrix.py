"""Codec/container smoke gate used before selecting a smaller FFmpeg payload."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import uuid
from pathlib import Path


MATRIX = {
    "mp4": ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"],
    "mkv": ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"],
    "webm": ["-c:v", "libvpx-vp9", "-c:a", "libopus", "-b:a", "128k"],
    "avi": ["-c:v", "copy", "-c:a", "libmp3lame", "-b:a", "192k"],
    "mov": ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"],
    "mp3": ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "wav": ["-vn", "-c:a", "pcm_s16le"],
    "flac": ["-vn", "-c:a", "flac"],
    "aac": ["-vn", "-c:a", "aac", "-b:a", "192k", "-f", "adts"],
    "opus": ["-vn", "-c:a", "libopus", "-b:a", "128k"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ffmpeg", type=Path)
    args = parser.parse_args()
    ffmpeg = str(args.ffmpeg.resolve())
    root = Path(__file__).resolve().parent / "runtime_tmp" / ("ffmpeg-matrix-" + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=True)
    try:
        source = root / "fixture.mp4"
        command = [
            ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            "testsrc=size=320x240:rate=10", "-f", "lavfi", "-i",
            "sine=frequency=880:sample_rate=44100", "-t", "1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ]
        subprocess.run(command, check=True)
        failures = []
        for extension, options in MATRIX.items():
            target = root / f"output.{extension}"
            result = subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), *options, str(target)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not target.exists() or target.stat().st_size < 100:
                failures.append({"format": extension, "stderr": result.stderr[-400:]})
        if failures:
            raise SystemExit(f"FFmpeg matrix failed: {failures}")
        print(f"FFmpeg matrix passed: {len(MATRIX)} formats")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
