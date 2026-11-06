"""Offline transport regressions: every update hop must verify TLS."""
import hashlib
import io
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

from app import app_update, updater, ytdlp_updater


def response(payload=b"", url=None):
    result = mock.MagicMock()
    result.__enter__.return_value = result
    result.read.return_value = payload
    result.geturl.return_value = url
    return result


class ReleaseTransportTests(unittest.TestCase):
    def test_linux_release_uses_verified_context_on_both_requests(self):
        worker = updater.UpdateWorker("1.0", manual=True)
        updates, errors = [], []
        worker.signals.update_available.connect(updates.append)
        worker.signals.error.connect(errors.append)
        asset = {"name": "app.AppImage", "browser_download_url": "https://example.invalid/app",
                 "digest": "sha256:" + "a" * 64, "size": 42}
        context = ssl.create_default_context()
        with mock.patch.object(updater, "IS_WINDOWS", False), \
                mock.patch.object(updater, "tls_context", return_value=context), \
                mock.patch.object(updater, "select_linux_asset", return_value=asset) as select, \
                mock.patch.object(updater.urllib.request, "urlopen", side_effect=[
                    response(url=updater.RELEASES_URL + "/tag/v2.0"), response(b"<html></html>")]) as request:
            worker.run()
        self.assertEqual(errors, [])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["sha256"], "a" * 64)
        select.assert_called_once()
        self.assertEqual(request.call_count, 2)
        for call in request.call_args_list:
            self.assertIs(call.kwargs["context"], context)
            self.assertEqual(call.kwargs["timeout"], 8)

    def test_certificate_failure_never_retries_without_verification(self):
        for manual in (False, True):
            for failed_hop in (0, 1):
                with self.subTest(manual=manual, failed_hop=failed_hop):
                    worker = updater.UpdateWorker("1.0", manual=manual)
                    errors, updates = [], []
                    worker.signals.error.connect(errors.append)
                    worker.signals.update_available.connect(updates.append)
                    failure = urllib.error.URLError(ssl.SSLCertVerificationError("untrusted CA"))
                    replies = [response(url=updater.RELEASES_URL + "/tag/v2.0")] * failed_hop + [failure]
                    with mock.patch.object(updater.urllib.request, "urlopen", side_effect=replies) as request:
                        worker.run()
                    self.assertEqual(request.call_count, failed_hop + 1)
                    self.assertEqual(updates, [])
                    self.assertEqual(len(errors), int(manual))
                    if manual:
                        self.assertIn("untrusted CA", errors[0])
                    for call in request.call_args_list:
                        context = call.kwargs["context"]
                        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                        self.assertTrue(context.check_hostname)

    def test_application_download_tls_failure_never_stages_or_changes_target(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "current.exe"
            target.write_bytes(b"original")
            worker = app_update.AppUpdateDownloadWorker({
                "download_url": "https://example.invalid/app.zip", "asset_name": "app.zip",
                "version": "2.0", "sha256": "a" * 64, "size": 1}, str(target))
            errors, staged = [], []
            worker.signals.error.connect(errors.append)
            worker.signals.staged.connect(lambda *args: staged.append(args))
            with mock.patch.object(app_update.urllib.request, "urlopen", side_effect=
                                   urllib.error.URLError(ssl.SSLCertVerificationError("untrusted CA"))) as request:
                worker.run()
            self.assertEqual(target.read_bytes(), b"original")
            self.assertFalse(Path(str(target) + ".update-new").exists())
            self.assertEqual(staged, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("untrusted CA", errors[0])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)


class EngineTransportTests(unittest.TestCase):
    @staticmethod
    def wheel():
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as wheel:
            wheel.writestr("yt_dlp/__init__.py", "")
            wheel.writestr("yt_dlp/version.py", "__version__ = '2026.1.1'")
        return data.getvalue()

    @staticmethod
    def metadata(payload):
        return json.dumps({"info": {"version": "2026.1.1"}, "releases": {"2026.1.1": [{
            "packagetype": "bdist_wheel", "filename": "yt_dlp-2026.1.1-py3-none-any.whl",
            "url": "https://example.invalid/engine.whl",
            "digests": {"sha256": hashlib.sha256(payload).hexdigest()}}]}}).encode()

    def test_metadata_and_wheel_use_verified_context_and_install(self):
        payload = self.wheel()
        context = ssl.create_default_context()
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(ytdlp_updater, "_runtime_root", return_value=Path(root)), \
                mock.patch.object(ytdlp_updater, "tls_context", return_value=context), \
                mock.patch.object(ytdlp_updater.urllib.request, "urlopen", side_effect=[
                    io.BytesIO(self.metadata(payload)), io.BytesIO(payload)]) as request:
            version, destination = ytdlp_updater._download_current_stable()
            self.assertEqual(version, "2026.1.1")
            self.assertTrue((destination / ".verified").is_file())
            self.assertTrue((destination / "yt_dlp/version.py").is_file())
            self.assertFalse(list(Path(root).glob("*.download")))
            self.assertEqual(request.call_count, 2)
            for call in request.call_args_list:
                self.assertIs(call.kwargs["context"], context)

    def test_failed_wheel_never_installs_and_removes_partial_file(self):
        payload = self.wheel()
        for failure in ("certificate", "interrupted", "checksum"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                if failure == "certificate":
                    wheel_response = urllib.error.URLError(ssl.SSLCertVerificationError("untrusted CA"))
                    expected = urllib.error.URLError
                elif failure == "interrupted":
                    wheel_response = response()
                    wheel_response.read.side_effect = [payload[:10], OSError("connection lost")]
                    expected = OSError
                else:
                    wheel_response = io.BytesIO(b"tampered wheel")
                    expected = ValueError
                with mock.patch.object(ytdlp_updater, "_runtime_root", return_value=Path(root)), \
                        mock.patch.object(ytdlp_updater.urllib.request, "urlopen", side_effect=[
                            io.BytesIO(self.metadata(payload)), wheel_response]) as request:
                    with self.assertRaises(expected):
                        ytdlp_updater._download_current_stable()
                self.assertEqual(list(Path(root).iterdir()), [])
                self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
