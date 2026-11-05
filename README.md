# YouTube Batch Downloader

A desktop app for downloading YouTube videos, playlists, or audio in batches on **Windows and Linux**.

Paste your links, choose a format and folder, then start downloading. **No browser extension is required.**

## Download and run

Open the **[latest release](https://github.com/kuy124/YoutubeBatchDownloader/releases/latest)** and choose the download for your computer. Version **1.9.6** includes Windows portable/installer and Linux portable/installer downloads:

| System | Download | How to run |
| --- | --- | --- |
| Windows | `YouTubeBatchDownloader-vX.Y.Z-Setup.exe` | Run the installer, then open the app from the Start Menu. |
| Windows portable | `YoutubeBatchDownloader-vX.Y.Z.zip` | Extract the ZIP and open `YouTubeBatchDownloader.exe`. |
| Linux portable | `YouTubeBatchDownloader-vX.Y.Z-linux-x86_64.AppImage` | Allow execution, then double-click or run it. No installation needed. |
| Ubuntu/Debian installer | `YouTubeBatchDownloader-vX.Y.Z-linux-amd64.deb` | Install with the command below, then open the app from your application menu. |
| Linux archive | `YouTubeBatchDownloader-vX.Y.Z-linux-x86_64.tar.gz` | Extract and run `./YouTubeBatchDownloader`; system dependencies are required. |

Windows downloads include the required tools; Python is not needed.

### Linux portable (AppImage)

```bash
chmod +x YouTubeBatchDownloader-*-linux-x86_64.AppImage
./YouTubeBatchDownloader-*-linux-x86_64.AppImage
```

The AppImage bundles the download tools and their libraries. If your system reports a FUSE error, run it with `--appimage-extract-and-run` instead. A graphical Linux desktop is required. Portable means no installation; settings still live in your user data folder.

### Ubuntu/Debian installer

Open a terminal in the folder containing the download:

```bash
sudo apt install ./YouTubeBatchDownloader-*-linux-amd64.deb
```

This adds an application-menu shortcut and installs the required tools automatically. To uninstall: `sudo apt remove youtubebatchdownloader`. Install a newer `.deb` the same way to update.

### Linux archive or source dependencies

On Ubuntu/Debian, install these once:

```bash
sudo apt update
sudo apt install ffmpeg aria2 nodejs libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 libxcb-keysyms1 libxcb-icccm4
```

For Fedora and Arch, try the AppImage rather than the `.deb`. Those distributions have not been tested yet. Replace the AppImage with the newer download to update.

The 1.9.6 release was built and startup-tested on Ubuntu 24.04 and requires an equivalent or newer system library stack. Older Ubuntu versions, Fedora, and Arch remain unverified; Ubuntu 22.04 compatibility needs a separate build from the GitHub Actions workflow.

## Your first download

1. Paste one or more YouTube links into the app, one per line.
2. Choose **MP4 Video** for video or **MP3 Audio** for audio.
3. Choose the quality and download folder.
4. Click **Add to Queue**, then **Start Queue**.

Playlist links expand into individual videos. You can pause, cancel, or retry downloads, and open the output folder from the app.

## Useful options

- **Batch downloads:** queue several videos or playlists together.
- **Video and audio formats:** choose the output you need, including MP4, MKV, MP3, and FLAC.
- **Download controls:** limit speed, skip existing files, and adjust simultaneous downloads.
- **Subtitles and metadata:** optional extras available in Settings.

### Videos that require sign-in

Leave **Settings → Network and Access → Cookies** set to **Disabled** for normal public videos.

If a video requires your account, optionally choose **From browser** and a browser where you are signed in, or select an existing Netscape-format **cookies.txt file**. Close your browser before retrying if its cookie database is locked. Windows may block Chrome/Edge/Brave cookie access; try Firefox instead.

Cookies do not bypass paid access or account restrictions. Cookie files contain private login information—never share them or upload them to an issue.

## Troubleshooting

- **A download fails:** retry it and check that the link opens in your browser. Some videos are private, removed, restricted, or temporarily blocked by YouTube.
- **Linux app does not open:** run it in a terminal to see the missing-library message, and install the dependencies above.
- **Need help:** open an issue with your OS, app version, and error message. Do not include cookies or other login information.

Only download content you own or have permission to download, and follow the site's terms and applicable law.

## Run or build from source

Requires Python 3.11+ and Git or a downloaded copy of the source.

**Windows:** run `install.bat`, then `run.bat`. To create release packages, run `build.bat` (requires the pinned Inno Setup compiler described in `packaging/toolchain.json`).

**Linux:** install the dependencies above plus `python3-venv`, then run:

```bash
bash install.sh
bash run.sh
```

To build all Linux packages (requires `curl`, `dpkg-deb`, and the dependencies above):

```bash
bash packaging/build_release_linux.sh
PYTHONPATH=. .venv-linux/bin/python packaging/check_linux_packages.py
```

The AppImage, `.deb`, archive, and SHA-256 checksums are written to `dist/`. Windows and Linux share the same source but are built separately on their own OS. The manual **Build Linux preview** GitHub Actions workflow produces all three formats; it does not publish a release. Build on the oldest supported Ubuntu: packages built on newer Ubuntu versions require newer glibc. To repackage an existing Linux build, run `bash packaging/package_linux.sh`.

Run tests with the virtual environment's Python:

```bash
python -m unittest discover -s tests -q
```
