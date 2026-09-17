import json
import os
import sys
from .utils import get_data_dir, get_install_dir, migrate_legacy_data
from .logger import log

class Settings:
    def __init__(self):
        migrate_legacy_data()
        self.settings_file = os.path.join(get_data_dir(), "settings.json")
        if getattr(sys, "frozen", False):
            downloads_base = os.path.join(os.path.expanduser("~"), "Downloads")
            self.default_downloads = os.path.join(downloads_base, "YouTubeBatchDownloader")
        else:
            downloads_base = os.path.join(get_install_dir(), "downloads")
            self.default_downloads = downloads_base
        
        # Clean defaults: Separate quality presets for videos and audios
        self.config = {
            "download_path": self.default_downloads,
            "format": "MP4 Video",
            "quality": "Best",
            "video_quality": "Best",
            "audio_quality": "192 kbps (High / Standard)",
            "audio_boost": "100% (Original)",
            "auto_clear": False,
            "monitor_clipboard": False,
            "theme": "Dark",
            "use_aria2": False,
            "completion_sound": True,
            "batch_notifications": True,
            "confirm_exit_downloading": True,
            "restore_links": False,
            "saved_links": "",
            "threads": max(12, (os.cpu_count() or 4) * 2)
        }
        self.load()
        self._migrate_legacy_download_path()

    def _migrate_legacy_download_path(self):
        """Moves only the old default path; custom paths remain untouched."""
        old_default = os.path.join(get_install_dir(), "downloads")
        if os.path.normcase(os.path.abspath(self.config.get("download_path", ""))) != os.path.normcase(os.path.abspath(old_default)):
            return
        if self.config.get("download_path") == self.default_downloads:
            return
        self.config["download_path"] = self.default_downloads
        self.save()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
                log.info("Settings loaded successfully.")
            except Exception as e:
                log.error(f"Failed to load settings: {str(e)}")

    def save(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            log.info("Settings saved successfully.")
        except Exception as e:
            log.error(f"Failed to save settings: {str(e)}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value, save=True):
        self.config[key] = value
        if save:
            self.save()

    def update(self, new_data: dict, save=True):
        self.config.update(new_data)
        if save:
            self.save()
