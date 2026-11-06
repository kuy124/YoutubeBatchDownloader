"""Regression checks for frozen Linux trust stores and external tools."""
import os
import ssl
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from app import network, platform_compat, utils


class TrustStoreTests(unittest.TestCase):
    def test_invalid_host_bundle_is_not_hidden_by_fallback(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(network.sys, "platform", "linux"), \
                mock.patch.object(network.os.path, "isfile", return_value=True), \
                mock.patch.object(network.ssl, "create_default_context") as create:
            create.return_value.load_verify_locations.side_effect = ssl.SSLError("invalid CA bundle")
            with self.assertRaises(ssl.SSLError):
                network.tls_context()
            create.return_value.load_verify_locations.assert_called_once_with(
                cafile="/etc/pki/tls/certs/ca-bundle.crt")

    def test_empty_overrides_still_load_fallback_roots(self):
        with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "", "SSL_CERT_DIR": ""}, clear=True), \
                mock.patch.object(network.os.path, "isfile", return_value=False), \
                mock.patch.object(network.ssl, "create_default_context") as create:
            network.tls_context()
            create.return_value.load_verify_locations.assert_called_once_with(cafile=network.certifi.where())

    def test_linux_uses_host_bundle_before_certifi(self):
        for bundle in ("/etc/pki/tls/certs/ca-bundle.crt",
                       "/etc/ssl/certs/ca-certificates.crt",
                       "/etc/ssl/ca-bundle.pem"):
            with self.subTest(bundle=bundle), \
                    mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(network.sys, "platform", "linux"), \
                    mock.patch.object(network.os.path, "isfile", side_effect=lambda p: p == bundle), \
                    mock.patch.object(network.ssl, "create_default_context") as create:
                context = network.tls_context()
                context.load_verify_locations.assert_called_once_with(cafile=bundle)
                self.assertIs(context, create.return_value)

    def test_missing_host_bundle_uses_packaged_roots(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(network.os.path, "isfile", return_value=False), \
                mock.patch.object(network.ssl, "create_default_context") as create:
            network.tls_context()
            create.return_value.load_verify_locations.assert_called_once_with(cafile=network.certifi.where())

    def test_admin_overrides_are_not_silently_replaced(self):
        for key in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
            with self.subTest(key=key), \
                    mock.patch.dict(os.environ, {key: "/custom/trust"}, clear=True), \
                    mock.patch.object(network.ssl, "create_default_context") as create:
                network.tls_context()
                create.return_value.load_verify_locations.assert_not_called()

    def test_context_verifies_certificates_and_hostnames(self):
        context = network.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)


class ExternalToolTests(unittest.TestCase):
    def test_frozen_linux_restores_loader_environment_without_mutating_parent(self):
        for original in (None, "", "/host/lib"):
            env = {"LD_LIBRARY_PATH": "/tmp/_MEI/lib", "PATH": "/usr/bin"}
            if original is not None:
                env["LD_LIBRARY_PATH_ORIG"] = original
            with self.subTest(original=original), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(platform_compat.sys, "platform", "linux"), \
                    mock.patch.object(platform_compat.sys, "frozen", True, create=True):
                result = platform_compat.external_tool_env()
                self.assertEqual(result.get("LD_LIBRARY_PATH"), original)
                self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/tmp/_MEI/lib")
                self.assertEqual(result["PATH"], "/usr/bin")

    def test_source_environment_is_unchanged(self):
        with mock.patch.object(platform_compat.sys, "frozen", False, create=True):
            self.assertEqual(platform_compat.external_tool_env(), dict(os.environ))

    def _find(self, results, executable=True):
        with mock.patch.object(utils.sys, "platform", "linux"), \
                mock.patch.object(utils.sys, "frozen", True, create=True), \
                mock.patch.object(utils.sys, "_MEIPASS", "/bundle", create=True), \
                mock.patch.object(utils, "tool_name", return_value="ffmpeg"), \
                mock.patch.object(utils, "get_install_dir", return_value="/install"), \
                mock.patch.object(utils.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                mock.patch.object(utils.os.path, "isfile", return_value=True), \
                mock.patch.object(utils.os, "access", return_value=executable), \
                mock.patch.object(utils.subprocess, "run", side_effect=results) as run:
            return utils.get_ffmpeg_path(), run

    def test_linux_prefers_working_system_ffmpeg(self):
        path, run = self._find([subprocess.CompletedProcess([], 0, b"ffmpeg version 7.1")])
        self.assertEqual(path, os.path.abspath("/usr/bin/ffmpeg"))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/ffmpeg", "-version"])
        self.assertEqual(run.call_count, 1)

    def test_broken_system_binary_falls_back_to_bundle(self):
        for failure in (OSError("missing loader"), subprocess.TimeoutExpired("ffmpeg", 5),
                        subprocess.CompletedProcess([], 127, b""),
                        subprocess.CompletedProcess([], 0, b"not ffmpeg")):
            with self.subTest(failure=failure):
                path, run = self._find([failure, subprocess.CompletedProcess([], 0, b"ffmpeg version 7")])
                self.assertEqual(path, os.path.abspath("/bundle/tools/ffmpeg"))
                self.assertEqual(run.call_count, 2)

    def test_non_executable_tools_are_not_selected(self):
        path, run = self._find([], executable=False)
        self.assertEqual(path, "")
        run.assert_not_called()

    def test_all_broken_candidates_return_missing(self):
        path, run = self._find([OSError("bad binary")] * 4)
        self.assertEqual(path, "")
        self.assertEqual(run.call_count, 4)


@unittest.skipUnless(os.name == "posix", "requires real POSIX executable permissions")
class NativeLinuxDiscoveryTests(unittest.TestCase):
    def test_real_executable_fallback_and_permissions(self):
        with tempfile.TemporaryDirectory(prefix="ffmpeg paths with spaces ") as root:
            system = Path(root) / "system" / "ffmpeg"
            bundled = Path(root) / "app" / "tools" / "ffmpeg"
            for path in (system, bundled):
                path.parent.mkdir(parents=True)
                path.write_text("#!/bin/sh\nprintf 'ffmpeg version test\\n'\n", encoding="utf-8")
                path.chmod(0o755)
            with mock.patch.object(utils.sys, "platform", "linux"), \
                    mock.patch.object(utils, "get_install_dir", return_value=str(bundled.parent.parent)), \
                    mock.patch.object(utils, "tool_name", return_value="ffmpeg"), \
                    mock.patch.object(utils.shutil, "which", return_value=str(system)), \
                    mock.patch.object(utils.sys, "frozen", False, create=True):
                self.assertEqual(utils.get_ffmpeg_path(), str(system))
                system.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
                self.assertEqual(utils.get_ffmpeg_path(), str(bundled))
                bundled.chmod(0o644)
                self.assertEqual(utils.get_ffmpeg_path(), "")


class FFmpegIntegrationTests(unittest.TestCase):
    def test_detected_binary_merges_separate_streams_with_ytdlp(self):
        from yt_dlp import YoutubeDL
        from yt_dlp.postprocessor.ffmpeg import FFmpegMergerPP

        ffmpeg = utils.get_ffmpeg_path()
        if not ffmpeg:
            self.skipTest("FFmpeg is not installed")
        with tempfile.TemporaryDirectory() as root:
            video = os.path.join(root, "video.mp4")
            audio = os.path.join(root, "audio.m4a")
            merged = os.path.join(root, "merged.mp4")
            for source, target, codec in (
                    ("color=c=black:s=64x64:r=5", video, ["-c:v", "mpeg4"]),
                    ("sine=frequency=440", audio, ["-c:a", "aac"])):
                subprocess.run(
                    [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                     source, "-t", "0.4", *codec, target], check=True,
                    capture_output=True, env=platform_compat.external_tool_env())
            with YoutubeDL({"ffmpeg_location": ffmpeg, "quiet": True}) as ydl:
                merger = FFmpegMergerPP(ydl)
                self.assertTrue(merger.available)
                merger.run({
                    "filepath": merged, "ext": "mp4",
                    "__files_to_merge": [video, audio],
                    "requested_formats": [
                        {"vcodec": "mpeg4", "acodec": "none", "protocol": "https"},
                        {"vcodec": "none", "acodec": "aac", "protocol": "https"}],
                })
                streams = merger.get_metadata_object(merged)["streams"]
            self.assertEqual({stream["codec_type"] for stream in streams}, {"video", "audio"})


if __name__ == "__main__":
    unittest.main()
