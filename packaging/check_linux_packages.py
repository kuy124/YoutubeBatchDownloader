"""Run on Linux after packaging: verify contents and offscreen GUI startup."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from app.updater import APP_VERSION


def check_startup(command, directory):
    marker = directory / "startup.json"
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(directory / "data"))
    with (directory / "startup.log").open("w+") as log:
        process = subprocess.Popen(
            [*command, "--startup-marker", str(marker)], env=environment,
            stdout=log, stderr=log, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 120
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.5)
            log.seek(0)
            assert marker.exists(), log.read()
            assert "first_paint" in json.loads(marker.read_text())["stages_ms"]
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=20)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    portable = root / "dist" / f"YouTubeBatchDownloader-{APP_VERSION}-linux-x86_64.AppImage"
    installer = root / "dist" / f"YouTubeBatchDownloader-{APP_VERSION}-linux-amd64.deb"
    for artifact in (portable, installer):
        subprocess.run(["sha256sum", "-c", artifact.name + ".sha256"], cwd=artifact.parent, check=True)
    with tempfile.TemporaryDirectory(prefix="ybd-packages-") as temporary:
        directory = Path(temporary)
        extracted = directory / "deb"
        subprocess.run(["dpkg-deb", "-x", str(installer), str(extracted)], check=True)
        assert (extracted / "usr/share/applications/youtubebatchdownloader.desktop").is_file()
        assert (extracted / "opt/youtubebatchdownloader/tools/ffmpeg").is_symlink()
        appimage_check = directory / "portable"
        appimage_check.mkdir()
        check_startup([str(portable), "--appimage-extract-and-run"], appimage_check)
        installer_check = directory / "installer"
        installer_check.mkdir()
        check_startup([str(extracted / "opt/youtubebatchdownloader/YouTubeBatchDownloader")], installer_check)
    print("AppImage and Debian installer checks passed (offscreen GUI).")
