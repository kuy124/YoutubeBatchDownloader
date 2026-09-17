import sys
import os
import threading

# Prevent PyInstaller library issues and handle environment paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.qt_runtime import prepare_qt_dll_search

prepare_qt_dll_search()

from PySide6.QtWidgets import QApplication

from app.logger import log
from app.splash import LoadingSplash
from app.app_update import acknowledge_updated_startup
from app.startup import StartupClock, marker_path_from_argv
from app.ytdlp_updater import prepare_ytdlp_runtime, warm_ytdlp_runtime


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
    clock = StartupClock(marker_path_from_argv(startup_args))

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
        if arg in ("--update-marker", "--update-backup", "--startup-marker"):
            skip_next = True
            continue
        if arg.startswith("--startup-marker="):
            continue
        qt_args.append(arg)
    app = QApplication(qt_args)
    clock.mark("qt_ready")

    # Modern styling fallback
    app.setStyle("Fusion")

    # Splash paints immediately so startup never looks frozen; the heavy
    # download stack (yt-dlp, mutagen) imports behind it in a visible stage.
    splash = LoadingSplash()
    splash.show()
    splash.start()
    app.processEvents()

    try:
        splash.set_message("Preparing the download engine...")
        app.processEvents()
        selection = prepare_ytdlp_runtime()
        clock.mark("runtime_path_ready")
        warm_result: dict = {}

        def warm_engine():
            warm_result.update(warm_ytdlp_runtime(selection))

        # Import the engine on a worker while the GUI module is being imported.
        # No network work occurs here; only the already verified local runtime is
        # activated, with the bundled copy as a safe fallback.
        warm_thread = threading.Thread(target=warm_engine, name="yt-dlp-warmup", daemon=True)
        warm_thread.start()

        splash.set_message("Loading interface...")
        app.processEvents()
        from app.gui import MainWindow
        clock.mark("gui_import_complete")

        splash.set_message("Preparing interface...")
        app.processEvents()
        window = MainWindow()
        clock.mark("window_constructed")
        warm_thread.join()
        ytdlp_status = warm_result or {"active_version": "Unavailable", "last_result": "Warmup failed"}
        clock.mark("runtime_ready")
        clock.mark("cached_runtime_ready")
        window.set_ytdlp_runtime_status(ytdlp_status)
        log.info(
            f"yt-dlp {ytdlp_status.get('active_version', 'unknown')}: "
            f"{ytdlp_status.get('last_result', '')}"
        )
        window.show()
        app.processEvents()
        clock.mark("first_paint")
        clock.write({"active_ytdlp": ytdlp_status.get("active_version", "Unavailable")})
        # Confirm a replacement immediately after the fully initialized local
        # interface is visible. Remote maintenance must not delay this signal.
        acknowledge_updated_startup(startup_args)
        window.start_background_maintenance(clock)
        clock.mark("background_checks_started")
        clock.write({"active_ytdlp": ytdlp_status.get("active_version", "Unavailable")})
    finally:
        splash.finish()

    exit_code = app.exec()
    log.info(f"Application closing with exit code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
