import random
import re
import urllib.request

from PySide6.QtCore import QObject, QRunnable, Signal

from .utils import insecure_ssl_context

APP_VERSION = "v1.7.0"


def parse_version(ver_str: str) -> tuple:
    cleaned = re.sub(r'[^0-9.]', '', ver_str)
    return tuple(map(int, cleaned.split('.'))) if cleaned else (0,)


class UpdateSignals(QObject):
    update_available = Signal(str, str)
    no_update = Signal(bool)
    error = Signal(str)


class UpdateWorker(QRunnable):
    def __init__(self, current_version: str, manual: bool = False):
        super().__init__()
        self.current_version = current_version
        self.manual = manual
        self.signals = UpdateSignals()

    def run(self):
        # A list of standard browser profiles to rotate through (Dynamic User)
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/117.0.2045.60'
        ]

        # Bypass API IP limits by hitting the frontend, and bypass bot-protection by rotating users
        url = "https://github.com/kuy124/YoutubeBatchDownloader/releases/latest"
        req = urllib.request.Request(url, headers={'User-Agent': random.choice(user_agents)})
        try:
            with urllib.request.urlopen(req, timeout=5, context=insecure_ssl_context()) as resp:
                final_url = resp.geturl()
                
                # Extract the tag version directly from the redirected URL
                if "releases/tag/" in final_url:
                    tag_name = final_url.split("releases/tag/")[-1].split('/')[0]
                    html_url = final_url
                    
                    if parse_version(tag_name) > parse_version(self.current_version):
                        self.signals.update_available.emit(tag_name, html_url)
                    else:
                        self.signals.no_update.emit(self.manual)
                else:
                    raise Exception("Failed to parse release version from GitHub.")
        except Exception as e:
            if self.manual:
                self.signals.error.emit(str(e))
