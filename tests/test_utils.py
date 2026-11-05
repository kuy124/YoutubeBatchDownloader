"""Unit tests for the pure helpers in app/utils.py.

Run from the repository root:
    venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""
import os
import tempfile
import unittest
from unittest import mock

from app.utils import (
    build_audio_boost_filter,
    build_cookies_options,
    build_subtitle_options,
    clean_youtube_url,
    escape_yt_dlp_template_literal,
    explain_cookie_failure,
    extract_http_links,
    extract_playlist_id,
    find_existing_output,
    format_display_title,
    format_elapsed_words,
    format_hms,
    is_expandable_playlist,
    is_mix_playlist,
    is_youtube_url,
    js_runtime_options,
    output_extension_for_format,
    parse_rate_limit,
    parse_subtitle_langs,
    playlist_url_for_expansion,
    private_cookiefile,
    sanitize_output_stem,
)


class CleanYoutubeUrlTests(unittest.TestCase):
    def test_strips_tracking_parameters_by_default(self):
        url = "https://www.youtube.com/watch?v=abc123&list=PLxyz&t=40s"
        self.assertEqual(clean_youtube_url(url), "https://www.youtube.com/watch?v=abc123")

    def test_keeps_a_real_playlist_when_asked(self):
        url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"
        self.assertEqual(
            clean_youtube_url(url, keep_playlist=True),
            "https://www.youtube.com/watch?v=abc123&list=PLxyz",
        )

    def test_always_drops_endless_mix_playlists(self):
        url = "https://www.youtube.com/watch?v=abc123&list=RDabc123"
        self.assertEqual(
            clean_youtube_url(url, keep_playlist=True),
            "https://www.youtube.com/watch?v=abc123",
        )

    def test_leaves_other_links_alone(self):
        url = "https://youtu.be/abc123"
        self.assertEqual(clean_youtube_url(url), url)


class PlaylistDetectionTests(unittest.TestCase):
    def test_watch_links_expand_through_the_playlist_url(self):
        self.assertEqual(
            playlist_url_for_expansion(
                "https://www.youtube.com/watch?v=hWJ5FnqQM1Q&list=PLZUHlX3bX-Nxa8j"),
            "https://www.youtube.com/playlist?list=PLZUHlX3bX-Nxa8j")

    def test_collection_urls_are_left_alone(self):
        for url in (
            "https://www.youtube.com/playlist?list=PLZUHlX3bX-Nxa8j",
            "https://www.youtube.com/@SomeChannel/videos",
            "https://www.youtube.com/channel/UC123",
            "",
        ):
            self.assertEqual(playlist_url_for_expansion(url), url)

    def test_endless_mixes_are_never_rewritten(self):
        url = "https://www.youtube.com/watch?v=abc&list=RDabc"
        self.assertEqual(playlist_url_for_expansion(url), url)

    def test_mix_detection(self):
        self.assertTrue(is_mix_playlist("RDabc123"))
        self.assertTrue(is_mix_playlist("rdabc123"))
        self.assertFalse(is_mix_playlist("PLabc123"))
        self.assertFalse(is_mix_playlist(""))

    def test_playlist_id_extraction(self):
        self.assertEqual(
            extract_playlist_id("https://www.youtube.com/watch?v=x&list=PL1"), "PL1")
        self.assertEqual(extract_playlist_id("https://youtu.be/x"), "")
        self.assertEqual(extract_playlist_id(""), "")

    def test_expandable_links(self):
        expandable = [
            "https://www.youtube.com/playlist?list=PL1",
            "https://www.youtube.com/channel/UC1234",
            "https://www.youtube.com/@somehandle",
            "https://www.youtube.com/watch?v=abc&list=PL1",
            "https://www.youtube.com/c/SomeChannel/videos",
        ]
        for url in expandable:
            self.assertTrue(is_expandable_playlist(url), url)

    def test_single_videos_are_not_expandable(self):
        for url in (
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
            "https://www.youtube.com/watch?v=abc&list=RDabc",
        ):
            self.assertFalse(is_expandable_playlist(url), url)

    def test_youtube_url_detection(self):
        self.assertTrue(is_youtube_url("https://youtu.be/x"))
        self.assertFalse(is_youtube_url("https://vimeo.com/x"))


class RateLimitTests(unittest.TestCase):
    def test_parses_display_values(self):
        self.assertEqual(parse_rate_limit("512 KB/s"), 512 * 1024)
        self.assertEqual(parse_rate_limit("1 MB/s"), 1024 ** 2)
        self.assertEqual(parse_rate_limit("5 MB/s"), 5 * 1024 ** 2)
        self.assertEqual(parse_rate_limit("25 MB/s"), 25 * 1024 ** 2)

    def test_unlimited_and_junk(self):
        self.assertIsNone(parse_rate_limit("No limit"))
        self.assertIsNone(parse_rate_limit(""))
        self.assertIsNone(parse_rate_limit(None))


class SubtitleTests(unittest.TestCase):
    def test_language_parsing(self):
        self.assertEqual(parse_subtitle_langs("en"), ["en"])
        self.assertEqual(parse_subtitle_langs("en, es-419"), ["en", "es-419"])
        self.assertEqual(parse_subtitle_langs("all"), ["all"])
        self.assertEqual(parse_subtitle_langs(""), ["all"])

    def test_off_produces_nothing(self):
        result = build_subtitle_options("Off", "en", "mp4")
        self.assertEqual(result['opts'], {})
        self.assertEqual(result['postprocessors'], [])

    def test_embed_into_a_capable_container(self):
        result = build_subtitle_options("Embed in video", "en", "mp4")
        self.assertTrue(result['opts']['writesubtitles'])
        self.assertTrue(result['opts']['writeautomaticsub'])
        self.assertEqual(result['opts']['subtitleslangs'], ["en"])
        self.assertEqual(result['postprocessors'], [{'key': 'FFmpegEmbedSubtitle'}])

    def test_embed_falls_back_for_avi(self):
        result = build_subtitle_options("Embed in video", "en", "avi")
        self.assertNotIn('subtitlesformat', result['opts'])
        self.assertEqual(result['postprocessors'], [])

    def test_sidecar_converts_to_srt(self):
        result = build_subtitle_options("Save as .srt file", "en,de", "mkv")
        self.assertEqual(result['opts']['subtitleslangs'], ["en", "de"])
        self.assertEqual(
            result['postprocessors'],
            [{'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}],
        )


class CookiesTests(unittest.TestCase):
    def test_app_bound_encryption_becomes_actionable(self):
        hint = explain_cookie_failure(
            "ERROR: Failed to decrypt with DPAPI. See  "
            "https://github.com/yt-dlp/yt-dlp/issues/10927  for more info")
        self.assertIn("App-Bound Encryption", hint)
        self.assertIn("Firefox", hint)

    def test_a_locked_cookie_database_says_to_close_the_browser(self):
        hint = explain_cookie_failure(
            "Could not copy Chrome cookie database. See "
            "https://github.com/yt-dlp/yt-dlp/issues/7271 for more info")
        self.assertIn("Close it completely", hint)

    def test_unrelated_errors_are_left_alone(self):
        self.assertIsNone(explain_cookie_failure("HTTP Error 403: Forbidden"))
        self.assertIsNone(explain_cookie_failure(""))
        self.assertIsNone(explain_cookie_failure(None))

    def test_disabled(self):
        self.assertEqual(build_cookies_options("Disabled", "chrome", ""), {})
        self.assertEqual(build_cookies_options("", "", ""), {})

    def test_from_browser(self):
        self.assertEqual(
            build_cookies_options("From browser", "Firefox", ""),
            {'cookiesfrombrowser': ('firefox', None, None, None)},
        )

    def test_browser_defaults_when_unset(self):
        self.assertEqual(
            build_cookies_options("From browser", "", ""),
            {'cookiesfrombrowser': ('chrome', None, None, None)},
        )

    def test_file_mode_requires_an_existing_file(self):
        self.assertEqual(build_cookies_options("cookies.txt file", "", r"Z:\nope.txt"), {})
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
            path = handle.name
        try:
            self.assertEqual(build_cookies_options("cookies.txt file", "", path),
                             {'cookiefile': path})
        finally:
            os.unlink(path)


class SkipExistingTests(unittest.TestCase):
    def test_finds_a_complete_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "My Video.mp4")
            with open(target, "wb") as handle:
                handle.write(b"not empty")
            self.assertEqual(
                find_existing_output(folder, "My Video", "MP4 Video"), target)

    def test_ignores_zero_byte_placeholders(self):
        with tempfile.TemporaryDirectory() as folder:
            open(os.path.join(folder, "My Video.mp4"), "wb").close()
            self.assertEqual(find_existing_output(folder, "My Video", "MP4 Video"), "")

    def test_missing_inputs_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(find_existing_output(folder, "Absent", "MP4 Video"), "")
            self.assertEqual(find_existing_output("", "My Video", "MP4 Video"), "")
            self.assertEqual(find_existing_output(folder, "", "MP4 Video"), "")
            self.assertEqual(find_existing_output(folder, "My Video", "Not a format"), "")

    def test_illegal_characters_match_the_written_name(self):
        with tempfile.TemporaryDirectory() as folder:
            stem = sanitize_output_stem('Bad: Name?', "MP4 Video")
            with open(os.path.join(folder, stem + ".mp4"), "wb") as handle:
                handle.write(b"x")
            self.assertEqual(
                find_existing_output(folder, 'Bad: Name?', "MP4 Video"),
                os.path.join(folder, stem + ".mp4"),
            )


class FilenameTests(unittest.TestCase):
    def test_illegal_characters_are_replaced(self):
        self.assertEqual(sanitize_output_stem('a<b>c:d"e|f?g*h', ""), "a_b_c_d_e_f_g_h")

    def test_reserved_device_names_are_suffixed(self):
        self.assertEqual(sanitize_output_stem("CON", ""), "CON_")

    def test_known_extension_is_stripped(self):
        self.assertEqual(sanitize_output_stem("Song.mp3", "MP3 Audio"), "Song")

    def test_trailing_dots_and_spaces_removed(self):
        self.assertEqual(sanitize_output_stem("Title...  ", ""), "Title")

    def test_blank_input(self):
        self.assertEqual(sanitize_output_stem("   ", ""), "")

    def test_long_names_are_truncated(self):
        self.assertEqual(len(sanitize_output_stem("x" * 400, "", max_length=180)), 180)

    def test_template_literals_escape_percent(self):
        self.assertEqual(escape_yt_dlp_template_literal("50% off"), "50%% off")

    def test_extensions(self):
        self.assertEqual(output_extension_for_format("MP3 Audio"), ".mp3")
        self.assertEqual(output_extension_for_format("Best Quality (MKV)"), ".mkv")
        self.assertEqual(output_extension_for_format("Unknown"), "")


class LinkExtractionTests(unittest.TestCase):
    def test_pulls_links_out_of_messy_text(self):
        text = 'see https://youtu.be/a and <https://www.youtube.com/watch?v=b>, done'
        self.assertEqual(
            extract_http_links(text),
            ["https://youtu.be/a", "https://www.youtube.com/watch?v=b"],
        )

    def test_empty_input(self):
        self.assertEqual(extract_http_links(""), [])
        self.assertEqual(extract_http_links(None), [])


class DisplayTests(unittest.TestCase):
    def test_uploader_prefix_is_added_once(self):
        self.assertEqual(format_display_title("Song", "Artist"), "Artist - Song")
        self.assertEqual(format_display_title("Artist - Song", "Artist"), "Artist - Song")

    def test_time_formatting(self):
        self.assertEqual(format_hms(65), "01:05")
        self.assertEqual(format_hms(3725), "01:02:05")
        self.assertEqual(format_elapsed_words(1), "1 second")
        self.assertEqual(format_elapsed_words(125), "2 minutes and 5 seconds")

    def test_boost_filter(self):
        self.assertIsNone(build_audio_boost_filter("100% (Original)"))
        boosted = build_audio_boost_filter("150% (+3.5 dB)")
        self.assertIn("volume=1.50", boosted)
        self.assertIn("alimiter", boosted)


class PrivateCookiefileTests(unittest.TestCase):
    """yt-dlp dumps its jar back into 'cookiefile', so the shared file must stay read-only."""

    def test_a_write_back_lands_in_the_copy_not_the_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("# Netscape HTTP Cookie File\n")
            with open(source, "rb") as handle:
                before = handle.read()

            with private_cookiefile(source) as copy:
                self.assertNotEqual(copy, source)
                with open(copy, "rb") as handle:
                    self.assertEqual(handle.read(), before)
                with open(copy, "w", encoding="utf-8") as handle:
                    handle.write("# poisoned by a rotated session token\n")

            with open(source, "rb") as handle:
                self.assertEqual(handle.read(), before)
            self.assertFalse(os.path.exists(copy))

    def test_no_cookie_file_means_no_copy(self):
        with private_cookiefile(None) as copy:
            self.assertIsNone(copy)

    def test_a_file_that_vanished_is_passed_through_so_yt_dlp_reports_it(self):
        absent = os.path.join(tempfile.gettempdir(), "definitely-absent-cookies.txt")
        with private_cookiefile(absent) as copy:
            self.assertEqual(copy, absent)

    def test_a_failed_copy_leaves_no_temporary_file_behind(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("# Netscape HTTP Cookie File\n")
            leftovers = set(os.listdir(tempfile.gettempdir()))
            with mock.patch("app.utils.write_cookie_copy", side_effect=OSError("denied")):
                with self.assertRaises(OSError):
                    with private_cookiefile(source):
                        pass
            self.assertEqual(set(os.listdir(tempfile.gettempdir())), leftovers)


class YouTubeSapisidFilterTests(unittest.TestCase):
    """YouTube answers "The page needs to be reloaded" when a request carries its
    SAPISID-family cookies without the SAPISIDHASH header only a browser can build.

    yt-dlp sends the cookies and never computes the hash, so every extraction came
    back empty and surfaced as "Requested format is not available". Dropping just
    those three names on the youtube.com domain was verified to restore the full
    43-format response while LOGIN_INFO and the PSID family stay behind.
    """

    HEADER = "# Netscape HTTP Cookie File\n# Generated by a test. Do not edit.\n\n"

    def row(self, domain, name, http_only=False):
        prefix = "#HttpOnly_" if http_only else ""
        return "\t".join([prefix + domain, "TRUE", "/", "TRUE", "1700000000", name, "v"]) + "\n"

    def names_in(self, path):
        with open(path, encoding="utf-8") as handle:
            rows = [line.rstrip("\n") for line in handle
                    if line.strip() and not line.startswith("# Netscape")
                    and not line.startswith("# Generated")]
        return [line.split("\t")[5] for line in rows if line.count("\t") == 6], rows

    def test_the_youtube_sapisid_family_is_dropped_from_the_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(self.HEADER)
                handle.write(self.row(".youtube.com", "SAPISID", http_only=True))
                handle.write(self.row(".youtube.com", "__Secure-1PAPISID", http_only=True))
                handle.write(self.row(".youtube.com", "__Secure-3PAPISID", http_only=True))
                handle.write(self.row("www.youtube.com", "SAPISID"))

            with private_cookiefile(source) as copy:
                names, _rows = self.names_in(copy)
            self.assertEqual(names, [])

    def test_the_google_sapisid_family_and_the_rest_of_the_login_survive(self):
        keepers = [
            self.row(".google.com", "SAPISID", http_only=True),
            self.row(".google.com", "__Secure-1PAPISID", http_only=True),
            self.row("accounts.google.com", "SAPISID"),
            self.row(".youtube.com", "LOGIN_INFO"),
            self.row(".youtube.com", "__Secure-1PSID", http_only=True),
            self.row(".youtube.com", "__Secure-3PSID", http_only=True),
            self.row(".youtube.com", "__Secure-1PSIDTS", http_only=True),
            self.row(".youtube.com", "HSID", http_only=True),
            self.row(".youtube.com", "SSID", http_only=True),
            self.row(".youtube.com", "SID"),
            self.row(".youtube.com", "PREF", http_only=True),
        ]
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(self.HEADER)
                handle.write(self.row(".youtube.com", "SAPISID", http_only=True))
                handle.writelines(keepers)

            with private_cookiefile(source) as copy:
                _names, rows = self.names_in(copy)
            self.assertEqual(rows, [line.rstrip("\n") for line in keepers])

    def test_a_file_without_those_names_is_copied_verbatim(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            body = self.HEADER + self.row(".youtube.com", "LOGIN_INFO") + self.row(".youtube.com", "SID")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(body)

            with private_cookiefile(source) as copy:
                with open(copy, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), body)

    def test_comments_and_malformed_rows_are_left_for_yt_dlp_to_judge(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            odd = "# a bare comment\n.not-a-cookie-row\n"
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(self.HEADER + odd + self.row(".youtube.com", "SAPISID"))

            with private_cookiefile(source) as copy:
                with open(copy, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), self.HEADER + odd)

    def test_the_source_file_is_never_rewritten_by_the_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "cookies.txt")
            body = self.HEADER + self.row(".youtube.com", "SAPISID", http_only=True)
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(body)

            with private_cookiefile(source):
                pass
            with open(source, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), body)


class JsRuntimeOptionsTests(unittest.TestCase):
    """yt-dlp enables only Deno by default, so a Node-only machine cannot solve
    YouTube's signature challenge and gets back storyboards instead of formats."""

    def test_every_runtime_yt_dlp_can_drive_is_named(self):
        runtimes = js_runtime_options()["js_runtimes"]
        self.assertEqual(set(runtimes), {"deno", "node", "bun", "quickjs"})
        self.assertTrue(all(config == {} for config in runtimes.values()))

    def test_each_call_is_a_fresh_dict_so_yt_dlp_cannot_poison_the_next_one(self):
        first = js_runtime_options()["js_runtimes"]
        first.pop("node")
        first["deno"]["path"] = "mutated"
        second = js_runtime_options()["js_runtimes"]
        self.assertIn("node", second)
        self.assertEqual(second["deno"], {})


if __name__ == "__main__":
    unittest.main()
