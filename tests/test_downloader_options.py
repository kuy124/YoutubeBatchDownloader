"""Unit tests for the yt-dlp option builders in app/downloader.py.

Run from the repository root:
    venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""
import os
import unittest

from app.downloader import (
    build_audio_postprocessor_args,
    build_format_options,
    build_merger_args,
    build_output_template,
    build_video_format_string,
    container_for_format,
    is_untrusted_path_error,
)


class OutputTemplateTests(unittest.TestCase):
    def test_empty_name_falls_back_to_the_video_title(self):
        self.assertEqual(
            build_output_template(r"C:\Out", "", "MP4 Video"),
            os.path.join(r"C:\Out", "%(title)s.%(ext)s"),
        )

    def test_custom_name_is_used_verbatim(self):
        self.assertEqual(
            build_output_template(r"C:\Out", "My Clip", "MP4 Video"),
            os.path.join(r"C:\Out", "My Clip.%(ext)s"),
        )

    def test_percent_signs_are_escaped_for_the_template(self):
        self.assertIn("50%%", build_output_template(r"C:\Out", "50% off", "MP4 Video"))


class FormatSelectorTests(unittest.TestCase):
    def test_uncapped_selector(self):
        selector = build_video_format_string(None)
        self.assertTrue(selector.startswith("bv*+"))
        self.assertIn("/b", selector)

    def test_capped_selector(self):
        selector = build_video_format_string("1080")
        self.assertIn("height<=1080", selector)

    def test_container_lookup(self):
        self.assertEqual(container_for_format("MP4 Video"), "mp4")
        self.assertEqual(container_for_format("WEBM Video"), "webm")
        self.assertEqual(container_for_format("Best Quality (MKV)"), "mkv")
        self.assertEqual(container_for_format("MP3 Audio"), "")


class FormatOptionsTests(unittest.TestCase):
    def test_mp4_video_merges_to_aac_and_embeds_art(self):
        opts = build_format_options("MP4 Video", "bv*+ba/b", "192", "192k", None)
        self.assertEqual(opts['merge_output_format'], "mp4")
        self.assertTrue(opts['writethumbnail'])
        keys = [pp['key'] for pp in opts['postprocessors']]
        self.assertIn("FFmpegMetadata", keys)
        self.assertIn("EmbedThumbnail", keys)
        self.assertEqual(
            opts['postprocessor_args']['merger'],
            ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k'],
        )

    def test_webm_never_embeds_art(self):
        opts = build_format_options("WEBM Video", "bv*+ba/b", "192", "192k", None)
        self.assertNotIn('writethumbnail', opts)
        self.assertEqual(opts['merge_output_format'], "webm")

    def test_mp3_defers_conversion_to_the_post_pass(self):
        opts = build_format_options("MP3 Audio", "", "320", "320k", None)
        self.assertEqual(opts['postprocessors'], [])
        self.assertFalse(opts['writethumbnail'])

    def test_lossless_audio_ignores_the_bitrate(self):
        opts = build_format_options("FLAC Audio", "", "320", "320k", None)
        extract = opts['postprocessors'][0]
        self.assertEqual(extract['preferredcodec'], 'flac')
        self.assertNotIn('preferredquality', extract)
        self.assertTrue(opts['writethumbnail'])

    def test_lossy_audio_keeps_the_bitrate(self):
        opts = build_format_options("M4A Audio", "", "256", "256k", None)
        self.assertEqual(opts['postprocessors'][0]['preferredquality'], "256")

    def test_unknown_format_falls_back_to_mkv(self):
        opts = build_format_options("Something New", "bv*+ba/b", "192", "192k", None)
        self.assertEqual(opts['merge_output_format'], "mkv")


class AudioFilterTests(unittest.TestCase):
    def test_merger_args_gain_the_boost_filter(self):
        self.assertEqual(
            build_merger_args("aac", "192k", "volume=1.50"),
            ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-filter:a', 'volume=1.50'],
        )

    def test_merger_args_without_a_boost(self):
        self.assertEqual(
            build_merger_args("aac", "192k", None),
            ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k'],
        )

    def test_postprocessor_args_only_when_boosting(self):
        self.assertEqual(build_audio_postprocessor_args(None), {})
        self.assertEqual(
            build_audio_postprocessor_args("volume=2.00"),
            {'extractaudio': ['-filter:a', 'volume=2.00']},
        )

    def test_avi_routes_the_boost_through_the_video_convertor(self):
        opts = build_format_options("AVI Video", "bv*+ba/b", "192", "192k", "volume=1.50")
        self.assertEqual(opts['postprocessor_args']['videoconvertor'],
                         ['-filter:a', 'volume=1.50'])


class UntrustedPathTests(unittest.TestCase):
    def test_winerror_448_is_detected(self):
        error = OSError("blocked")
        error.winerror = 448
        self.assertTrue(is_untrusted_path_error(error))

    def test_message_is_detected(self):
        self.assertTrue(is_untrusted_path_error(RuntimeError("Untrusted mount point")))

    def test_unrelated_errors_pass_through(self):
        self.assertFalse(is_untrusted_path_error(RuntimeError("403 Forbidden")))


if __name__ == "__main__":
    unittest.main()
