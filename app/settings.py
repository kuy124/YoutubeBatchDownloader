import json
import os
from .utils import get_root_dir
from .logger import log

class Settings:
    def __init__(self):
        self.settings_file = os.path.join(get_root_dir(), "settings.json")
        self.default_downloads = os.path.join(get_root_dir(), "downloads")
        
        # Clean defaults: MP3 Audio format, 480p quality, no active checkboxes on launch
        self.config = {
            "download_path": self.default_downloads,
            "format": "MP3 Audio",
            "quality": "480p",
            "merge_auto": False,
            "embed_thumbnail": False,
            "embed_metadata": False,
            "threads": 3
        }
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Merge existing values on top of clean defaults
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

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()