import logging
import os
from .utils import get_root_dir

def setup_logger():
    """Sets up the application logger."""
    log_dir = os.path.join(get_root_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    logger = logging.getLogger("AppLogger")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

log = setup_logger()