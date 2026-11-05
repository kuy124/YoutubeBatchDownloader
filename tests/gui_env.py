"""Test helpers shared by the GUI test modules."""

import tempfile
from contextlib import contextmanager
from unittest import mock


@contextmanager
def isolated_settings():
    """Points Settings at a throwaway data directory for one test.

    MainWindow persists preferences while it is being built, so a GUI test that
    does not isolate the data directory silently overwrites the real
    settings.json sitting beside the checkout.
    """
    with tempfile.TemporaryDirectory() as data_dir:
        with mock.patch("app.settings.get_data_dir", return_value=data_dir), \
                mock.patch("app.settings.migrate_legacy_data", return_value=None):
            yield data_dir
