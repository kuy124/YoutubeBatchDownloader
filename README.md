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

You can run the application instantly as a standalone program or set it up from the source code.

### Option A: Download the Standalone Executable
You do not need to install Python, FFmpeg, or manage command-line dependencies. 
1. Go to the **Release** section on this repository page.
2. Download the latest `YouTubeBatchDownloader.exe`.
3. Move the file to any directory or USB drive and run it. 
   *(This single `.exe` is entirely self-contained and pre-packaged with a lightweight FFmpeg binary).*

### Option B: Run from Source
If you prefer to run the application using your own local Python runtime:

#### Step 1: Install Python
Ensure you have Python 3.11 or newer installed.
1. Download it from the [Official Python Downloads Page](https://www.python.org/downloads/).
2. Run the installer and check the box to **"Add python.exe to PATH"** before finishing.

#### Step 2: Install Dependencies
1. Extract the project folder to your desired directory.
2. Double-click **`install.bat`**. This automatically creates a localized virtual environment (`venv`), installs all required libraries, and creates the folder structure. 
3. *Note: If FFmpeg is missing from your system, the script will automatically fetch a lightweight, safe binary (v4.4.1, ~37MB) from ffbinaries and place it in your `tools/` folder.*

#### Step 3: Run the Program
* Double-click **`run.bat`** to launch the graphical interface.

---

## Building a Standalone Executable

If you modify the source code and want to compile your own self-contained executable:

1. Double-click **`build.bat`**.
2. The compiler script uses PyInstaller to bundle your code, standard libraries, and the `tools/ffmpeg.exe` binary into a single file.
3. Once completed, your custom **`YouTubeBatchDownloader.exe`** will be ready inside the newly created **`dist/`** folder.

---

## How to Use

The application interface is designed to make batch queue management straightforward:

1. **Paste Target Links:** Enter your YouTube URLs (one link per line) in the primary text area. You can also **drag & drop links** anywhere onto the window, and any YouTube link already on your clipboard is loaded automatically at startup. Playlist URLs are supported — enable **Expand playlists** in the options chip and each video will be queued as its own numbered row.
2. **Configure Download Options:** Click the compact **options chip** (e.g. `MP4 · Best`) to open the *Download Options* dialog — pick your **Format** (*Best Quality*, *MP4 Video*, *MP3 Audio*...), cap the **Quality**, set an **Audio Boost**, and toggle playlist expansion. Your choices stay visible on the main window at a glance.
3. **Set Download Location:** The application automatically creates and defaults to a local `downloads/` directory. You can use the **Browse** button to select any other folder or drive.
4. **Download:** Click **Add to Queue and Download** or simply press **Ctrl+Enter**. You can safely monitor download progress, speeds, and estimated times of arrival in real-time from the status table. If any downloads fail, the **Retry All Failed** button appears automatically.

Handy extras: right-click any row in the queue for *Open File / Open Folder / Copy URL / Retry / Cancel / Remove*, duplicate links are skipped automatically, and overall batch progress is mirrored on the Windows taskbar with a tray notification when everything finishes.

---

## Understanding Key Features

* <span style="color:#2980b9"><b>Responsive Multithreading:</b></span> Download queues are offloaded to dedicated background worker threads. The GUI never hangs, stutters, or goes into an "Unresponsive" state, even during massive high-speed downloads.
* <span style="color:#27ae60"><b>Universal Codec Priority:</b></span> Instead of downloading raw `.webm` (VP9/AV1) streams that cause playback errors in legacy editors, the engine automatically remuxes downloads into globally accepted MP4 (H.264 + AAC) files.
* <span style="color:#e67e22"><b>Smart URL Safeguards:</b></span> To prevent accidental infinite loops, the program intelligently detects dynamic YouTube Mixes or watch-and-playlist combo links and strips them down to single-video downloads.
* <span style="color:#8e44ad"><b>Zero-Registry Portable Design:</b></span> The application does not write data to your Windows registry or system folders. It is entirely self-contained and runs safely on restricted user profiles without requiring administrator privileges.
* <span style="color:#00897b"><b>Full-Bandwidth Engine:</b></span> Up to eight videos download simultaneously and audio tracks run in their own wide pool, so fast connections stay saturated instead of idling. Power users on gigabit lines can opt into the bundled aria2c multi-connection engine by adding `"use_aria2": true` to `settings.json`. A per-download speed limiter and adjustable concurrency cap keep things under control.
* <span style="color:#5e35b1"><b>Frictionless Input:</b></span> Drag & drop links onto the window, press <b>Ctrl+Enter</b> to start, and let duplicate-link detection keep your queue clean automatically. Clipboard monitoring is debounced and batched — copying several links in a row results in one tidy add instead of popup spam.
* <span style="color:#1565c0"><b>Playlist Expansion:</b></span> Paste a playlist URL with **Expand playlists** enabled and each video queues as its own numbered row (01 - Title, 02 - Title ...). Expansion runs in the background with a visible placeholder row and a per-playlist cancel button.
* <span style="color:#455a64"><b>Dark & Light Themes:</b></span> The interface ships in a sleek dark theme by default, switchable to light anytime from **Settings → System Preferences** — applied live and remembered across sessions.
* <span style="color:#00695c"><b>System Preferences:</b></span> Fine-tune the app in **Settings → System Preferences**: completion sound, finish notifications, an exit confirmation while downloads run, optional link-list restore, playlist expansion, per-download speed limit, simultaneous video download cap, open-folder-after-batch, and a post-batch power action (shutdown or sleep).
* <span style="color:#c62828"><b>Blazing MP3 Conversion:</b></span> Audio extraction uses benchmark-tuned LAME settings, and audio tasks get a dedicated pool that converts whole batches in parallel across every CPU core — a 20-song queue finishes its conversions several times faster than serial encoding.
* <span style="color:#d32f2f"><b>Retry All Failed:</b></span> A dynamic **Retry All Failed** button appears automatically in the action bar when any download fails — one click retries every failed row at once.

---

## Troubleshooting

* **How to view detailed error logs:** If a download fails, check the detailed output and exception reports located in `logs/app.log`.
* **Download says "Failed: FFmpeg required...":** YouTube hosts audio and video streams separately. If you are running from source and chose MP3, the program needs `ffmpeg.exe` to convert the stream safely. Run `install.bat` to automatically acquire the missing binary in your `tools/` folder.
* **Blocked Requests (HTTP 403 / Forbidden Error):** If YouTube blocks your automated download requests, your local downloader library may be outdated. Open your command prompt inside the project folder, activate your virtual environment, and run:
  ```cmd
  pip install --upgrade yt-dlp
  ```
* **Want even faster downloads?** By default the app balances speed and stability. If your internet line is very fast (gigabit+), open `settings.json` and set `"use_aria2": true` to enable the bundled aria2c engine, which splits each file into 16 parallel connections. Note: per-row progress bars update less frequently while this mode is active, and progress returns to normal once each file finishes its download phase.

<hr>

<details>
  <summary><b>License</b> <i>(Click to expand)</i></summary>
  <br>
  <p>This project is open-source and distributed under the <strong>MIT License</strong>.</p>
</details>