import sys
import os

# Prevent PyInstaller library issues and handle environment paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from app.gui import MainWindow
from app.logger import log

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to ensure crashes are written to log."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

def main():
    log.info("Application starting...")
    app = QApplication(sys.argv)
    
    # Modern styling fallback
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    exit_code = app.exec()
    log.info(f"Application closing with exit code {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()