#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
    echo 'Build on x86_64 Linux (Ubuntu 22.04 or newer).' >&2; exit 1;
}
for tool in ffmpeg ffprobe aria2c node; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
python3 -m venv .venv-linux
python=.venv-linux/bin/python
"$python" -m pip install -r requirements.txt 'pyinstaller==6.19.0'
version=$("$python" -c 'from app.updater import APP_VERSION; print(APP_VERSION)')
stage="build/linux-release/YouTubeBatchDownloader"
mkdir -p "$stage/tools" dist
"$python" -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name YouTubeBatchDownloader --distpath "$stage" --workpath build/linux-app \
    --specpath build --paths "$PWD" --add-data "$PWD/icon.ico:." \
    --collect-all yt_dlp --collect-all yt_dlp_ejs --hidden-import mutagen \
    --exclude-module PySide6.QtWebEngine --exclude-module tkinter app/main.py
for tool in ffmpeg ffprobe aria2c node; do
    cp "$(command -v "$tool")" "$stage/tools/$tool"
done
printf '%s\n' 'Run ./YouTubeBatchDownloader. Requires a Linux desktop and system libraries for Qt, ffmpeg, aria2 and Node.js. See README.md for dependencies.' > "$stage/README.txt"
archive="dist/YouTubeBatchDownloader-${version}-linux-x86_64.tar.gz"
tar -czf "$archive" -C build/linux-release YouTubeBatchDownloader
sha256sum "$archive" > "$archive.sha256"
echo "Linux release ready: $archive"
bash packaging/package_linux.sh
