import json
import re
import urllib.request

from PySide6.QtCore import QObject, QRunnable, Signal

APP_VERSION = "v1.9.2"
RELEASE_API_URL = "https://api.github.com/repos/kuy124/YoutubeBatchDownloader/releases/latest"
USER_AGENT = "YouTubeBatchDownloader-Updater"


def parse_version(ver_str: str) -> tuple:
    parts = re.findall(r'\d+', ver_str or '')
    return tuple(map(int, parts)) if parts else (0,)


def select_windows_asset(assets: list) -> dict:
    candidates = []
    for asset in assets or []:
        name = str(asset.get('name') or '')
        lower = name.lower()
        if "youtubebatchdownloader" not in lower:
            continue
        if lower.endswith('.zip'):
            priority = 0
        elif lower.endswith('.exe'):
            priority = 1
        else:
            continue
        if asset.get('browser_download_url'):
            candidates.append((priority, lower, asset))
    if not candidates:
        raise ValueError("This release does not contain a Windows application asset.")
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


class UpdateSignals(QObject):
    update_available = Signal(dict)
    no_update = Signal(bool)
    error = Signal(str)


class UpdateWorker(QRunnable):
    def __init__(self, current_version: str, manual: bool = False):
        super().__init__()
        self.current_version = current_version
        self.manual = manual
        self.signals = UpdateSignals()

    def run(self):
        req = urllib.request.Request(RELEASE_API_URL, headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                release = json.loads(resp.read().decode('utf-8'))
            tag_name = str(release.get('tag_name') or '')
            if not tag_name:
                raise ValueError("GitHub did not return a release version.")
            if parse_version(tag_name) <= parse_version(self.current_version):
                self.signals.no_update.emit(self.manual)
                return

            asset = select_windows_asset(release.get('assets') or [])
            digest = str(asset.get('digest') or '')
            if not digest.lower().startswith('sha256:'):
                raise ValueError("The release asset does not provide a SHA-256 digest.")
            self.signals.update_available.emit({
                'version': tag_name,
                'html_url': release.get('html_url') or '',
                'asset_name': asset.get('name') or '',
                'download_url': asset['browser_download_url'],
                'size': int(asset.get('size') or 0),
                'sha256': digest.split(':', 1)[1].lower(),
            })
        except Exception as e:
            if self.manual:
                self.signals.error.emit(str(e))
