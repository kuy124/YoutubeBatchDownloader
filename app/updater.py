import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import urllib.request

from PySide6.QtCore import QObject, QRunnable, Signal

APP_VERSION = "v1.9.5"
RELEASES_URL = "https://github.com/kuy124/YoutubeBatchDownloader/releases"
USER_AGENT = "YouTubeBatchDownloader-Updater"


def parse_version(ver_str: str) -> tuple:
    parts = re.findall(r'\d+', ver_str or '')
    return tuple(map(int, parts)) if parts else (0,)


class ReleaseAssetsParser(HTMLParser):
    """Read download links and their checksums from GitHub's public asset list."""

    def __init__(self, tag: str):
        super().__init__()
        self.download_prefix = urlsplit(RELEASES_URL).path + '/download/' + tag + '/'
        self.assets = []
        self.asset = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            self.asset = {}
        if self.asset is None:
            return
        href = attrs.get('href') or ''
        if tag == 'a' and href.startswith(self.download_prefix):
            self.asset.update(name=unquote(href.rsplit('/', 1)[-1]),
                              browser_download_url='https://github.com' + href)
        if tag == 'clipboard-copy':
            self.handle_data(attrs.get('value') or '')

    def handle_data(self, data):
        if self.asset is not None:
            match = re.fullmatch(r'\s*sha256:([0-9a-fA-F]{64})\s*', data)
            if match:
                self.asset['digest'] = 'sha256:' + match[1].lower()

    def handle_endtag(self, tag):
        if tag == 'li' and self.asset is not None:
            if self.asset.get('browser_download_url'):
                self.assets.append(self.asset)
            self.asset = None


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
        req = urllib.request.Request(RELEASES_URL + '/latest', headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                release_url = resp.geturl()
            if not release_url.startswith(RELEASES_URL + '/tag/'):
                raise ValueError("GitHub did not return a release version.")
            tag = release_url[len(RELEASES_URL + '/tag/'):]
            tag_name = unquote(tag)
            if not tag_name:
                raise ValueError("GitHub did not return a release version.")
            if parse_version(tag_name) <= parse_version(self.current_version):
                self.signals.no_update.emit(self.manual)
                return

            req = urllib.request.Request(RELEASES_URL + '/expanded_assets/' + tag,
                                         headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=8) as resp:
                parser = ReleaseAssetsParser(tag)
                parser.feed(resp.read().decode('utf-8'))
            asset = select_windows_asset(parser.assets)
            digest = str(asset.get('digest') or '')
            if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
                raise ValueError("The release asset does not provide a SHA-256 digest.")
            self.signals.update_available.emit({
                'version': tag_name,
                'html_url': release_url,
                'asset_name': asset.get('name') or '',
                'download_url': asset['browser_download_url'],
                'size': int(asset.get('size') or 0),
                'sha256': digest.split(':', 1)[1].lower(),
            })
        except Exception as e:
            if self.manual:
                self.signals.error.emit(str(e))
