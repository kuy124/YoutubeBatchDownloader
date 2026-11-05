import os
import tempfile
import unittest
from unittest import mock

from app import platform_compat, updater, utils
from app.settings import Settings


class LinuxCompatibilityTests(unittest.TestCase):
    def test_linux_data_paths_and_tools(self):
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": root}), \
                mock.patch.object(platform_compat, "IS_WINDOWS", False), \
                mock.patch.object(utils.sys, "frozen", True, create=True):
            self.assertEqual(utils.get_data_dir(), os.path.join(root, "YouTubeBatchDownloader"))
            self.assertEqual(platform_compat.tool_name("ffmpeg"), "ffmpeg")

    def test_release_assets_cannot_cross_platforms(self):
        linux = {"name": "YouTubeBatchDownloader-v1.9.5-linux-x86_64.tar.gz",
                 "browser_download_url": "https://example.com/linux"}
        windows = {"name": "YouTubeBatchDownloader-v1.9.5-windows.zip",
                   "browser_download_url": "https://example.com/windows"}
        self.assertEqual(updater.select_linux_asset([windows, linux]), linux)
        self.assertEqual(updater.select_windows_asset([linux, windows]), windows)
        with self.assertRaises(ValueError):
            updater.select_windows_asset([linux])
        with self.assertRaises(ValueError):
            updater.select_linux_asset([windows])

    def test_removed_cookie_mode_does_not_supply_credentials(self):
        self.assertEqual(utils.build_cookies_options("From extension"), {})

    def test_linux_update_prefers_portable_appimage(self):
        archive = {"name": "YouTubeBatchDownloader-v2-linux-x86_64.tar.gz", "browser_download_url": "archive"}
        portable = {"name": "YouTubeBatchDownloader-v2-linux-x86_64.AppImage", "browser_download_url": "portable"}
        installer = {"name": "YouTubeBatchDownloader-v2-linux-amd64.deb", "browser_download_url": "installer"}
        self.assertEqual(updater.select_linux_asset([archive, installer, portable]), portable)

    def test_old_extension_setting_becomes_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"cookies_mode": "From extension"}')
            with mock.patch("app.settings.get_data_dir", return_value=folder), \
                    mock.patch("app.settings.migrate_legacy_data"):
                self.assertEqual(Settings().get("cookies_mode"), "Disabled")


if __name__ == "__main__":
    unittest.main()
