# YouTube Batch Downloader

A lightweight, high-reliability Windows desktop application for batch downloading YouTube videos. This tool processes downloads in the background, keeping the user interface completely responsive. It is designed to be highly resilient against network errors and does not require administrative privileges.

---

## Quick Setup Guide

### Step 1: Install Python
The application requires Python 3.11 or newer to run.
1. Download Python from the [Official Python Downloads Page](https://www.python.org/downloads/).
2. Run the downloaded installer.
3. **CRITICAL STEP:** Before clicking "Install Now", make sure to check the box at the bottom that says **"Add python.exe to PATH"**. If you skip this, the installer scripts will fail.

### Step 2: Extract & Install Dependencies
1. Extract this project folder to your desired location (e.g., your Desktop, a USB drive, etc.).
2. Double-click the **`install.bat`** file. 
3. A command window will appear and automatically set up your isolated environment and install the required libraries. This process will create three empty folders: `downloads/`, `logs/`, and `tools/`.

### Step 3: Run the Application
- Once installation finishes, double-click **`run.bat`** to start the downloader GUI.

---

## Maximizing Quality: Adding FFmpeg (Highly Recommended but Optional)

While the application is designed to download videos successfully without any extra tools, YouTube stores high-definition streams (1080p, 1440p, 4K) separately from audio. 

To merge these streams automatically or convert videos to high-quality **MP3s**, you should provide **FFmpeg**:

1. Go to the [FFmpeg Windows Builds page (gyan.dev)](https://www.gyan.dev/ffmpeg/builds/).
2. Scroll down to the **"release builds"** section and download `ffmpeg-release-essentials.zip`.
3. Open the downloaded `.zip` file, navigate inside the `bin` folder, and find **`ffmpeg.exe`**.
4. Copy **`ffmpeg.exe`** and paste it directly into the **`tools/`** folder inside your project directory:
   ```text
   YouTubeBatchDownloader/
   ├── tools/
   │   └── ffmpeg.exe   <-- Paste here
   ```

*Note: If `ffmpeg.exe` is missing, the downloader will automatically fall back to downloading pre-merged lower-resolution files (usually up to 720p or 360p depending on availability) so your download never crashes.*

---

## How to Use the App

1. **Paste Links:** Copy your target YouTube URLs and paste them into the large text box (one URL per line).
   * *Note: Playlists are not supported to prevent endless loops. If you paste a playlist link, the downloader will automatically extract and download only the primary video from that link.*
2. **Select Format & Quality:** 
   * **Format:** Choose *Best Quality*, *MP4 Video*, or *MP3 Audio* (Defaults to MP3).
   * **Max Quality:** Choose *Best*, *1080p*, *720p*, or *480p* (Defaults to 480p).
3. **Deactivated Checkboxes:** Advanced processing choices (merging, thumbnails, metadata) are unchecked by default to maximize speed and stability. Check them only if you have placed `ffmpeg.exe` in the `tools/` folder.
4. **Download Path:** Click **Browse** to change where files are saved (defaults to the `downloads/` folder in your project directory).
5. **Download:** Click **Add to Queue and Download**. The process starts immediately, and you can track the exact status, download speed, and ETA in the table.
6. **Cancel:** Click the **Cancel** button on any active download row to stop it.

---

## Advanced: Package into a Standalone `.exe`

If you want to package the application into a single executable file that you can share or run without launch scripts:
1. Double-click **`build.bat`**.
2. It will activate the virtual environment and package the app using PyInstaller.
3. Once completed, your final application, **`YouTubeBatchDownloader.exe`**, will be available inside the **`dist/`** folder.

---

## Troubleshooting & Help

### The download immediately says "Failed: ..."
* **Outdated downloader engine:** YouTube regularly changes its platform, which can break older versions of the downloader. Open your terminal in the virtual environment and run `pip install --upgrade yt-dlp` to update it, or delete the `venv` folder and run `install.bat` again.
* **Age-restricted/Private Videos:** The downloader cannot access videos that require a login, are marked private, or are age-restricted.

### Where can I find detailed errors?
If a download fails or behaves unexpectedly, check the log file located at:
`logs/app.log`
This text file records startup steps, detailed engine reports, and exact error codes, which are incredibly useful for debugging.