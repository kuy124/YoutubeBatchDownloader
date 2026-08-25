import json
import os
from .utils import get_root_dir
from .logger import log

class Settings:
    def __init__(self):
        self.settings_file = os.path.join(get_root_dir(), "settings.json")
        self.default_downloads = os.path.join(get_root_dir(), "downloads")
        
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
            "expand_playlists": False,
            "max_speed_mb": 0,
            "max_video_downloads": 8,
            "power_action": "None",
            "open_folder_after": False,
            "threads": max(12, (os.cpu_count() or 4) * 2)
        }
        self.load()

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

    def set(self, key, value):
        self.config[key] = value
        self.save()