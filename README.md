# YouTube Batch Downloader

A lightweight Windows desktop application for downloading YouTube videos in batches. Built with Python, PySide6, and `yt-dlp`, this tool runs downloads in the background to ensure the user interface remains responsive.

To maximize compatibility across different media players and video editors, the application prioritizes H.264 (AVC) video and AAC audio formats.

---

## Features
- **Responsive GUI**: Asynchronous multi-threaded downloads prevent the interface from freezing.
- **Universal Codec Compatibility**: Automatically prioritizes standard H.264 and AAC formats instead of AV1/Opus, ensuring your files play natively on default Windows Media Player and standard video editors.
- **Auto-Packaging with FFmpeg**: The build system automatically downloads and packages a lightweight FFmpeg binary inside the standalone executable.
- **Smart Safeguards**: 
  - Dynamic YouTube Mixes or combined watch-and-playlist links are stripped to single-video downloads to prevent infinite loops.
  - Safe error reporting if you attempt MP3 downloads without a local or global FFmpeg dependency.
- **Zero-Registry, Portable Design**: Runs from any directory, USB drive, or folder without requiring administrator privileges.

---

## Quick Start Guide

### Step 1: Install Python
The application requires Python 3.11 or newer to run.
1. Download Python from the [Official Python Downloads Page](https://www.python.org/downloads/).
2. Run the installer and check **"Add python.exe to PATH"** before finishing.

### Step 2: Install Dependencies
1. Extract the project folder to your desired path.
2. Double-click **`install.bat`**. This sets up a localized virtual environment (`venv`), installs libraries, and creates folder structures. If FFmpeg is missing, it automatically downloads a lightweight binary (v4.4.1, ~37MB) from *ffbinaries* into the `tools/` folder.

### Step 3: Run the Application
- Double-click **`run.bat`** to open the interface.

---

## Building a Standalone Executable (`.exe`)

The build script creates a single executable file that requires no external dependencies, python runtime, or separate FFmpeg installations.

1. Double-click **`build.bat`**.
2. The script compiles the application using PyInstaller, automatically bundles `tools/ffmpeg.exe`, and outputs **`YouTubeBatchDownloader.exe`** into the newly created **`dist/`** folder.
3. You can move this single `.exe` to any Windows computer and it will work immediately.

---

## Usage & Settings

1. **Paste Links**: Enter your YouTube links (one per line) in the text box. Playlist links are automatically processed as single-video downloads to avoid system hangs.
2. **Download Options**: 
   - **Format**: Select *Best Quality*, *MP4 Video*, or *MP3 Audio* (Defaults to MP3).
   - **Max Quality**: Select *Best*, *1080p*, *720p*, or *480p* (Defaults to 480p).
3. **Download Path**: The application defaults to the `downloads/` directory. You can use the **Browse** button to select another directory.
4. **Queue Management**: Click **Add to Queue and Download**. Track progress, speed, and ETAs directly from the main status table.

---

## Troubleshooting

- **How to view detailed errors**: The application outputs debug information and detailed exception reports into `logs/app.log`.
- **Download says "Failed: FFmpeg required..."**: YouTube does not serve raw MP3 files. It serves `.webm` or `.m4a` files. If you run the script directly and do not have `ffmpeg.exe` in your `tools/` folder or global system PATH, the application will prevent silent `.webm` downloads by failing cleanly. Run `install.bat` or `build.bat` to automatically acquire the binary.
- **Blocked Requests (HTTP 403 / Forbidden)**: If YouTube blocks standard automated requests, verify your local packages are up to date. Within your command prompt, activate the virtual environment and run:
  ```cmd
  pip install --upgrade yt-dlp