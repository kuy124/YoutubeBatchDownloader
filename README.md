<div align="center">
  <h1>YouTube Batch Downloader</h1>
  <p>
    <b>An asynchronous, multi-threaded Windows desktop utility designed for downloading YouTube videos in batches safely and efficiently.</b>
  </p>
</div>

Downloading videos or audio shouldn't freeze your desktop or output unplayable files. YouTube Batch Downloader is a lightweight, zero-registry GUI tool built with Python, PySide6, and `yt-dlp`. It runs all active downloads asynchronously in the background so the user interface remains completely responsive.

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

1. **Paste Target Links:** Enter your YouTube URLs (one link per line) in the primary text area.
2. **Configure Download Options:**
   * **Format:** Select *Best Quality*, *MP4 Video*, or *MP3 Audio*.
   * **Max Resolution:** Cap the quality at *Best*, *1080p*, *720p*, or *480p*.
3. **Set Download Location:** The application automatically creates and defaults to a local `downloads/` directory. You can use the **Browse** button to select any other folder or drive.
4. **Download:** Click **Add to Queue and Download**. You can safely monitor download progress, speeds, and estimated times of arrival in real-time from the status table.

---

## Understanding Key Features

* <span style="color:#2980b9"><b>Responsive Multithreading:</b></span> Download queues are offloaded to dedicated background worker threads. The GUI never hangs, stutters, or goes into an "Unresponsive" state, even during massive high-speed downloads.
* <span style="color:#27ae60"><b>Universal Codec Priority:</b></span> Instead of downloading raw `.webm` (VP9/AV1) streams that cause playback errors in legacy editors, the engine automatically remuxes downloads into globally accepted MP4 (H.264 + AAC) files.
* <span style="color:#e67e22"><b>Smart URL Safeguards:</b></span> To prevent accidental infinite loops, the program intelligently detects dynamic YouTube Mixes or watch-and-playlist combo links and strips them down to single-video downloads.
* <span style="color:#8e44ad"><b>Zero-Registry Portable Design:</b></span> The application does not write data to your Windows registry or system folders. It is entirely self-contained and runs safely on restricted user profiles without requiring administrator privileges.

---

## Troubleshooting

* **How to view detailed error logs:** If a download fails, check the detailed output and exception reports located in `logs/app.log`.
* **Download says "Failed: FFmpeg required...":** YouTube hosts audio and video streams separately. If you are running from source and chose MP3, the program needs `ffmpeg.exe` to convert the stream safely. Run `install.bat` to automatically acquire the missing binary in your `tools/` folder.
* **Blocked Requests (HTTP 403 / Forbidden Error):** If YouTube blocks your automated download requests, your local downloader library may be outdated. Open your command prompt inside the project folder, activate your virtual environment, and run:
  ```cmd
  pip install --upgrade yt-dlp
  ```

<hr>

<details>
  <summary><b>License</b> <i>(Click to expand)</i></summary>
  <br>
  <p>This project is open-source and distributed under the <strong>MIT License</strong>.</p>
</details>