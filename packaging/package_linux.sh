#!/usr/bin/env bash
# Package an already-built Linux application; no Python rebuild needed.
set -euo pipefail
cd "$(dirname "$0")/.."
python=.venv-linux/bin/python
version=$("$python" -c 'from app.updater import APP_VERSION; print(APP_VERSION)')
stage="$PWD/build/linux-release/YouTubeBatchDownloader"
[[ -x "$stage/YouTubeBatchDownloader" ]] || { echo 'Run build_release_linux.sh first.' >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
appdir="$work/YouTubeBatchDownloader.AppDir"
mkdir -p "$appdir/usr/lib" "$appdir/usr/share/icons/hicolor/256x256/apps" dist
cp -a "$stage/." "$appdir/usr/"
cat > "$appdir/AppRun" <<'EOF'
#!/bin/sh
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export LD_LIBRARY_PATH="$root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$root/usr/YouTubeBatchDownloader" "$@"
EOF
chmod 755 "$appdir/AppRun"
cat > "$appdir/youtubebatchdownloader.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=YouTube Batch Downloader
Comment=Download videos, playlists and audio
Exec=youtubebatchdownloader %U
Icon=youtubebatchdownloader
Terminal=false
Categories=AudioVideo;Network;
EOF
QT_QPA_PLATFORM=offscreen "$python" -c 'from PySide6.QtGui import QGuiApplication,QImage; import sys; app=QGuiApplication([]); image=QImage("icon.ico"); assert not image.isNull(); assert image.scaled(256,256).save(sys.argv[1])' "$appdir/youtubebatchdownloader.png"
cp "$appdir/youtubebatchdownloader.png" "$appdir/usr/share/icons/hicolor/256x256/apps/"
ln -s youtubebatchdownloader.png "$appdir/.DirIcon"
# Bundle tool and X11 plugin dependencies, but use the host's glibc/loader.
# Build on the oldest supported Ubuntu to set the glibc compatibility floor.
"$python" - "$stage/tools" "$appdir/usr/lib" <<'PY'
import pathlib, re, shutil, subprocess, sys
tools, destination = map(pathlib.Path, sys.argv[1:])
plugins = pathlib.Path('.venv-linux/lib').glob('python*/site-packages/PySide6/Qt/plugins/platforms/libqxcb.so')
for binary in [*tools.iterdir(), *plugins]:
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True, check=True)
    if 'not found' in result.stdout:
        raise SystemExit(f'Missing dependencies for {binary}:\n{result.stdout}')
    for name, path in re.findall(r'^\s*(\S+) => (/\S+)', result.stdout, re.M):
        if name.startswith(('libc.so', 'libm.so', 'libpthread.so', 'libdl.so', 'librt.so', 'libresolv.so', 'libutil.so', 'libQt6')):
            continue
        shutil.copy2(path, destination / name)
PY
# Pin and verify a versioned external packaging tool (not the moving continuous tag).
tool="$work/appimagetool.AppImage"
curl -fL --retry 3 https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage -o "$tool"
echo "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0  $tool" | sha256sum -c -
chmod 755 "$tool"
(cd "$work" && "$tool" --appimage-extract >/dev/null)
portable="$PWD/dist/YouTubeBatchDownloader-${version}-linux-x86_64.AppImage"
ARCH=x86_64 "$work/squashfs-root/AppRun" --no-appstream "$appdir" "$portable"

debroot="$work/deb"
mkdir -p "$debroot/DEBIAN" "$debroot/opt/youtubebatchdownloader/tools" "$debroot/usr/bin" "$debroot/usr/share/applications" "$debroot/usr/share/icons/hicolor/256x256/apps"
cp "$stage/YouTubeBatchDownloader" "$debroot/opt/youtubebatchdownloader/"
for toolname in ffmpeg ffprobe aria2c node; do
    ln -s "/usr/bin/$toolname" "$debroot/opt/youtubebatchdownloader/tools/$toolname"
done
ln -s /opt/youtubebatchdownloader/YouTubeBatchDownloader "$debroot/usr/bin/youtubebatchdownloader"
cp "$appdir/youtubebatchdownloader.desktop" "$debroot/usr/share/applications/"
cp "$appdir/youtubebatchdownloader.png" "$debroot/usr/share/icons/hicolor/256x256/apps/"
glibc=$(getconf GNU_LIBC_VERSION | cut -d' ' -f2)
cat > "$debroot/DEBIAN/control" <<EOF
Package: youtubebatchdownloader
Version: ${version#v}
Section: video
Priority: optional
Architecture: amd64
Maintainer: YoutubeBatchDownloader contributors <noreply@github.com>
Homepage: https://github.com/kuy124/YoutubeBatchDownloader
Depends: libc6 (>= $glibc), libstdc++6, ffmpeg, aria2, nodejs, libegl1, libopengl0, libxcb-cursor0, libxkbcommon-x11-0, libxcb-keysyms1, libxcb-icccm4
Installed-Size: $(du -sk "$debroot/opt" | cut -f1)
Description: Batch video and audio downloader
 Download videos and playlists with a graphical queue powered by yt-dlp.
EOF
chmod 755 "$debroot/opt/youtubebatchdownloader/YouTubeBatchDownloader"
installer="dist/YouTubeBatchDownloader-${version}-linux-amd64.deb"
dpkg-deb --root-owner-group --build "$debroot" "$installer"
for artifact in "$portable" "$installer"; do
    (cd dist && sha256sum "$(basename "$artifact")" > "$(basename "$artifact").sha256")
done
echo "Linux portable and installer ready in dist/"
