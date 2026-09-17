<div align="center">
  <h1>YouTube Batch Downloader</h1>
  <p>
    <b>An asynchronous, multi-threaded Windows desktop utility designed for downloading YouTube videos in batches safely and efficiently.</b>
  </p>
</div>

Downloading videos or audio shouldn't freeze your desktop or output unplayable files. YouTube Batch Downloader is a lightweight, zero-registry GUI tool built with Python, PySide6, and `yt-dlp`. It launches through an instant loading screen (heavy libraries load behind it), and runs all active downloads asynchronously in the background so the user interface remains completely responsive.

To guarantee maximum playback compatibility across default video players and standard video editors, the downloader automatically prioritizes standard **H.264 (AVC) video** and **AAC audio** formats instead of less-supported formats like AV1 or Opus.

<hr>

## Quick Start & Installation

You can install the application with the Windows setup program or run it from source.

### Option A: Install for Windows
You do not need to install Python, FFmpeg, or manage command-line dependencies.
1. Go to the **Release** section on this repository page.
2. Download `YouTubeBatchDownloader-vX.Y.Z-Setup.exe`.
3. Run the setup program. It installs for your Windows account, creates a Start Menu shortcut, and can optionally create a desktop shortcut.

The installed folder contains only the self-contained application executable. Settings, logs, and the verified yt-dlp runtime are kept separately in your user profile so updates do not clutter the install folder.

The matching portable ZIP remains available for users who specifically need a folder or USB copy. Its updater-compatible layout is `YoutubeBatchDownloader/YouTubeBatchDownloader.exe`.

### Option B: Run from Source
If you prefer to run the application using your own local Python runtime:

#### Step 1: Install Python
Ensure you have Python 3.11 or newer installed.
1. Download it from the [Official Python Downloads Page](https://www.python.org/downloads/).
2. Run the installer and check the box to **"Add python.exe to PATH"** before finishing.

#### Step 2: Install Dependencies
1. Extract the project folder to your desired directory.
2. Double-click **`install.bat`**. This automatically creates a localized virtual environment (`venv`), installs all required libraries, and creates the folder structure. 
3. *Note: If FFmpeg is missing from your system, the script will automatically fetch the pinned lightweight binary and place it in your `tools/` folder.*

#### Step 3: Run the Program
* Double-click **`run.bat`** to launch the graphical interface.

---

## Building a Standalone Executable

If you modify the source code and want to compile a release:

1. Double-click **`build.bat`**.
2. The script uses PyInstaller to bundle your code, standard libraries, and the `tools/ffmpeg.exe` binary into a single file.
3. Install the pinned Inno Setup 6.7.3 compiler and set `ISCC_PATH` if `ISCC.exe` is not in the standard install location. The build verifies the compiler hash before packaging.
4. The completed release is organized as:
   - `dist/installer/YouTubeBatchDownloader-vX.Y.Z-Setup.exe`
   - `dist/portable/YoutubeBatchDownloader-vX.Y.Z.zip`
   - `dist/metadata/` for hashes and the release manifest

---

## How to Use

The application interface is designed to make batch queue management straightforward:

1. **Paste Target Links:** Enter your YouTube URLs (one link per line) in the primary text area. You can also **drag & drop links** anywhere onto the window, and any YouTube link already on your clipboard is loaded automatically at startup.
2. **Configure Download Options:** Click the compact **⚙ options chip** (e.g. `MP4 · Best`) to open the *Download Options* dialog. Pick your **Format** (*Best Quality*, *MP4 Video*, *MP3 Audio*…), cap the **Quality**, set an **Audio Boost**, and toggle behavior preferences. Your choices stay visible on the main window at a glance.
3. **Set Download Location:** The installed application defaults to `Downloads/YouTubeBatchDownloader`. You can use the **Browse** button to select any other folder or drive.
4. **Prepare the Queue:** Click **Add to Queue** or press **Ctrl+Enter**. Each item remains in the Ready state so you can double-click its **Output Name** cell, press **F2**, or use **Rename Output** from the right-click menu. Leave the name empty to use the original video title.
5. **Start Downloads:** Click **Start Queue** or press **Ctrl+Shift+Enter**. You can monitor progress, speeds, and estimated completion times in the status table.

Handy extras: right-click any row in the queue for *Rename Output / Open File / Open Folder / Copy URL / Retry / Cancel / Remove*. Duplicate links are skipped automatically, and overall batch progress is mirrored on the Windows taskbar with a tray notification when everything finishes.

---

## Understanding Key Features

* <span style="color:#2980b9"><b>Responsive Multithreading:</b></span> Download queues are offloaded to dedicated background worker threads. The GUI never hangs, stutters, or goes into an "Unresponsive" state, even during massive high-speed downloads.
* <span style="color:#27ae60"><b>Universal Codec Priority:</b></span> Instead of downloading raw `.webm` (VP9/AV1) streams that cause playback errors in legacy editors, the engine automatically remuxes downloads into globally accepted MP4 (H.264 + AAC) files.
* <span style="color:#e67e22"><b>Smart URL Safeguards:</b></span> To prevent accidental infinite loops, the program intelligently detects dynamic YouTube Mixes or watch-and-playlist combo links and strips them down to single-video downloads.
* <span style="color:#8e44ad"><b>Per-User Installation:</b></span> The setup program installs without administrator privileges. Settings, logs, and runtime maintenance stay in your user profile while the install directory remains clean.
* <span style="color:#00897b"><b>Full-Bandwidth Engine:</b></span> Up to eight videos download simultaneously and audio tracks run in their own wide pool, so fast connections stay saturated instead of idling. Power users on gigabit lines can opt into the bundled aria2c multi-connection engine by adding `"use_aria2": true` to `settings.json`.
* <span style="color:#5e35b1"><b>Frictionless Input:</b></span> Drag and drop links onto the window, press <b>Ctrl+Enter</b> to stage them, rename outputs as needed, then press <b>Ctrl+Shift+Enter</b> to start. Clipboard monitoring is debounced and batched, so copying several links in a row results in one tidy add instead of popup spam.
* <span style="color:#455a64"><b>Curated Theme Collection:</b></span> Choose from dark, light, warm, cool, green, editorial, and high-contrast palettes from **Download Options → Theme**. Changes apply live and are remembered across sessions.
* <span style="color:#00695c"><b>Behavior Controls:</b></span> Fine-tune the app in **Settings → System Preferences**: completion sound and finish notifications on/off, an exit confirmation while downloads run, and optional link-list restore between sessions.
* <span style="color:#c62828"><b>Fast MP3 Conversion:</b></span> Audio extraction uses benchmark-tuned LAME settings, and audio tasks get a dedicated pool that converts whole batches in parallel across available CPU cores.
* <span style="color:#455a64"><b>Automatic Maintenance:</b></span> Packaged releases can download, verify, replace, and restart the current executable after one confirmation. The app also checks once daily for a verified stable yt-dlp update and falls back to the last working copy if the check fails.

---

## Troubleshooting

* **How to view detailed error logs:** If a download fails, check `logs/app.log` inside `%LOCALAPPDATA%\YouTubeBatchDownloader` for an installed copy, or the project `logs/` folder in source mode.
* **Download says "Failed: FFmpeg required...":** YouTube hosts audio and video streams separately. If you are running from source and chose MP3, the program needs `ffmpeg.exe` to convert the stream safely. Run `install.bat` to automatically acquire the missing binary in your `tools/` folder.
* **Blocked Requests (HTTP 403 / Forbidden Error):** Restart the application so its automatic yt-dlp check can run. The active yt-dlp version and last update result are shown under **Settings → Updates**.
* **Want even faster downloads?** By default the app balances speed and stability. If your internet line is very fast (gigabit+), open `settings.json` and set `"use_aria2": true` to enable the bundled aria2c engine, which splits each file into 16 parallel connections. Note: per-row progress bars update less frequently while this mode is active, and progress returns to normal once each file finishes its download phase.

<hr>

<details>
  <summary><b>License</b> <i>(Click to expand)</i></summary>
  <br>
  <p>This project is open-source and distributed under the <strong>MIT License</strong>.</p>
</details>
