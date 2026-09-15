import sys
import os

# Prevent PyInstaller library issues and handle environment paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from app.logger import log
from app.splash import LoadingSplash
from app.app_update import acknowledge_updated_startup
from app.ytdlp_updater import bootstrap_ytdlp


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to ensure crashes are written to log."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


def main():
    log.info("Application starting...")
    startup_args = list(sys.argv)

    # Force Windows shell to associate custom title bar icon with the taskbar icon slot
    try:
        import ctypes
        myappid = 'windows.downloader.yt-dlp.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    qt_args = [sys.argv[0]]
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg in ("--update-marker", "--update-backup"):
            skip_next = True
            continue
        qt_args.append(arg)
    app = QApplication(qt_args)

    # Modern styling fallback
    app.setStyle("Fusion")

    # Splash paints immediately so startup never looks frozen; the heavy
    # download stack (yt-dlp, mutagen) imports behind it in a visible stage.
    splash = LoadingSplash()
    splash.show()
    app.processEvents()

    try:
        splash.set_message("Checking the download engine...")
        app.processEvents()
        ytdlp_status = bootstrap_ytdlp(splash.set_message)
        log.info(
            f"yt-dlp {ytdlp_status.get('active_version', 'unknown')}: "
            f"{ytdlp_status.get('last_result', '')}"
        )

        splash.set_message("Loading download engine (yt-dlp)...")
        app.processEvents()
        from app.gui import MainWindow  # Heavy import happens here, visibly

        splash.set_message("Preparing interface...")
        app.processEvents()
        window = MainWindow()
        window.show()
        app.processEvents()
        acknowledge_updated_startup(startup_args)
    finally:
        splash.finish()

    exit_code = app.exec()
    log.info(f"Application closing with exit code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
