import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QObject, QRunnable, Signal

from .logger import log
from .utils import get_data_dir, migrate_legacy_data


PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
USER_AGENT = "YouTubeBatchDownloader-yt-dlp-Updater"
_STATUS = {
    "active_version": "Bundled",
    "last_result": "Not checked yet",
    "last_check": 0,
}
_ACTIVE_RUNTIME_PATH: Path | None = None


def version_tuple(value: str) -> tuple:
    parts = []
    for token in str(value or "").replace('-', '.').split('.'):
        if token.isdigit():
            parts.append(int(token))
        elif parts:
            break
    return tuple(parts) if parts else (0,)


def _runtime_root() -> Path:
    return Path(get_data_dir()) / "runtime" / "yt-dlp"


def _state_path() -> Path:
    return _runtime_root() / "state.json"


def _read_state() -> dict:
    try:
        with _state_path().open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
            if isinstance(state, dict):
                return state
    except (OSError, ValueError):
        pass
    return {}


def _write_state(state: dict) -> None:
    root = _runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    temp_path = root / "state.json.tmp"
    with temp_path.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)
    os.replace(temp_path, _state_path())


def _safe_wheel_member(name: str) -> bool:
    path = PurePosixPath(name.replace('\\', '/'))
    has_drive = bool(path.parts and ':' in path.parts[0])
    return not path.is_absolute() and not has_drive and ".." not in path.parts


def install_verified_wheel(wheel_path: Path, destination: Path) -> None:
    """Extracts a verified wheel into a fresh version directory."""
    temp_destination = destination.with_name(destination.name + ".installing")
    if temp_destination.exists():
        shutil.rmtree(temp_destination)
    temp_destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            members = wheel.infolist()
            if any(not _safe_wheel_member(member.filename) for member in members):
                raise ValueError("The yt-dlp wheel contains an unsafe archive path.")
            if not any(member.filename == "yt_dlp/__init__.py" for member in members):
                raise ValueError("The downloaded wheel does not contain yt_dlp.")
            for member in members:
                if member.is_dir():
                    continue
                relative = Path(*PurePosixPath(member.filename).parts)
                target = temp_destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with wheel.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        (temp_destination / ".verified").write_text("verified", encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temp_destination, destination)
    except Exception:
        shutil.rmtree(temp_destination, ignore_errors=True)
        raise


def _select_wheel(release_files: list) -> dict:
    wheels = [
        item for item in release_files or []
        if item.get("packagetype") == "bdist_wheel"
        and str(item.get("filename") or "").endswith("-py3-none-any.whl")
    ]
    if not wheels:
        raise ValueError("PyPI did not provide a universal yt-dlp wheel.")
    return wheels[0]


def _download_current_stable(status_callback=None) -> tuple[str, Path]:
    request = urllib.request.Request(PYPI_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=8) as response:
        metadata = json.loads(response.read().decode("utf-8"))
    version = str(metadata.get("info", {}).get("version") or "")
    if not version or not re.fullmatch(r'[0-9A-Za-z.+-]+', version):
        raise ValueError("PyPI did not return a yt-dlp version.")
    wheel = _select_wheel(metadata.get("releases", {}).get(version) or [])
    digest = str(wheel.get("digests", {}).get("sha256") or "").lower()
    if not digest:
        raise ValueError("PyPI did not provide a SHA-256 digest for yt-dlp.")

    destination = _runtime_root() / version
    if (destination / ".verified").exists():
        return version, destination

    if status_callback:
        status_callback(f"Updating download engine to yt-dlp {version}...")
    _runtime_root().mkdir(parents=True, exist_ok=True)
    wheel_path = _runtime_root() / f"{version}.whl.download"
    hasher = hashlib.sha256()
    try:
        wheel_request = urllib.request.Request(wheel["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(wheel_request, timeout=30) as response, wheel_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                hasher.update(chunk)
        if hasher.hexdigest().lower() != digest:
            raise ValueError("The yt-dlp download failed SHA-256 verification.")
        install_verified_wheel(wheel_path, destination)
    finally:
        try:
            wheel_path.unlink()
        except OSError:
            pass
    return version, destination


def _verified_versions() -> list[tuple[tuple, str, Path]]:
    root = _runtime_root()
    if not root.exists():
        return []
    versions = []
    for child in root.iterdir():
        if child.is_dir() and (child / ".verified").exists():
            versions.append((version_tuple(child.name), child.name, child))
    return sorted(versions, reverse=True)


def _prune_verified_versions(keep: int = 2) -> None:
    """Retains the active runtime and one verified rollback version."""
    root = _runtime_root().resolve()
    for _, _, old_path in _verified_versions()[keep:]:
        resolved = old_path.resolve()
        if resolved.parent == root and (resolved / ".verified").is_file():
            shutil.rmtree(resolved)


def _activate(path: Path | None) -> str:
    global _ACTIVE_RUNTIME_PATH
    if path is not None and str(path) not in sys.path:
        sys.path.insert(0, str(path))
    import yt_dlp
    _ACTIVE_RUNTIME_PATH = path
    return str(yt_dlp.version.__version__)


def _discard_failed_runtime(path: Path | None) -> None:
    if path is not None:
        try:
            sys.path.remove(str(path))
        except ValueError:
            pass
    for module_name in list(sys.modules):
        if module_name == "yt_dlp" or module_name.startswith("yt_dlp."):
            del sys.modules[module_name]


def prepare_ytdlp_runtime() -> dict:
    """Select the newest verified local runtime without importing or using network.

    This is intentionally tiny and synchronous: it only reads ``state.json`` and
    inspects ``.verified`` directories.  The actual engine import is performed by
    :func:`warm_ytdlp_runtime` on a startup worker while the GUI module loads.
    """
    global _STATUS
    # Migrate a legacy portable runtime before selecting the active version so
    # the first packaged launch can use the user's verified engine immediately.
    migrate_legacy_data()
    state = _read_state()
    verified = _verified_versions()
    selected_path = verified[0][2] if verified else None
    selected_version = verified[0][1] if verified else ""
    _STATUS = {
        "last_check": int(state.get("last_check") or 0),
        "active_version": str(state.get("active_version") or (selected_version or "Bundled")),
        "runtime_version": selected_version or str(state.get("runtime_version") or ""),
        "last_result": str(state.get("last_result") or "Not checked yet"),
    }
    return {"path": selected_path, "version": selected_version, "state": dict(_STATUS)}


def warm_ytdlp_runtime(selection: dict | None = None) -> dict:
    """Import the prepared engine and fall back safely to the bundled copy."""
    global _STATUS
    selection = selection or prepare_ytdlp_runtime()
    selected_path = selection.get("path")
    selected_version = str(selection.get("version") or "")
    state = dict(_STATUS)
    try:
        active_version = _activate(selected_path)
        if selected_path is not None:
            _prune_verified_versions(keep=2)
        state.update({
            "active_version": active_version,
            "runtime_version": selected_version or active_version,
        })
    except Exception as runtime_exc:
        log.warning("Verified yt-dlp runtime could not be imported; using bundled copy: %s", runtime_exc)
        _discard_failed_runtime(selected_path)
        try:
            active_version = _activate(None)
            state.update({
                "active_version": active_version,
                "runtime_version": "",
                "last_result": f"Verified runtime failed; using bundled yt-dlp: {runtime_exc}",
            })
        except Exception as bundled_exc:
            state.update({
                "active_version": "Unavailable",
                "runtime_version": "",
                "last_result": f"Could not load yt-dlp: {bundled_exc}",
            })
    try:
        _write_state(state)
    except OSError:
        pass
    _STATUS = dict(state)
    return dict(_STATUS)


def check_and_install_update(status_callback=None) -> dict:
    """Check PyPI and stage a verified runtime without hot-swapping imports."""
    global _STATUS
    state = _read_state()
    now = int(time.time())
    last_check = int(state.get("last_check") or 0)
    active_version = str(state.get("active_version") or _STATUS.get("active_version") or "Bundled")
    if now - last_check < CHECK_INTERVAL_SECONDS:
        result = dict(_STATUS)
        result.update({"state": "not_due", "last_check": last_check, "active_version": active_version})
        return result

    try:
        version, installed_path = _download_current_stable(status_callback)
        if version_tuple(version) > version_tuple(active_version):
            last_result = f"Stable {version} is ready; restart required"
            result_state = "restart_required"
        else:
            last_result = f"yt-dlp {active_version} is current"
            result_state = "current"
        state.update({
            "last_check": now,
            "active_version": active_version,
            "runtime_version": version,
            "last_result": last_result,
        })
    except Exception as exc:
        result_state = "failed"
        log.warning("Background yt-dlp update check failed: %s", exc)
        state.update({
            "last_check": now,
            "active_version": active_version,
            "last_result": f"Update check failed: {exc}",
        })
    try:
        _write_state(state)
    except OSError:
        pass
    _STATUS = dict(state)
    result = dict(_STATUS)
    result["state"] = result_state
    return result


class YtDlpUpdateSignals(QObject):
    progress = Signal(str)
    finished = Signal(dict)


class YtDlpUpdateWorker(QRunnable):
    """Runs the once-per-day PyPI maintenance check after first paint."""
    def __init__(self):
        super().__init__()
        self.signals = YtDlpUpdateSignals()

    def run(self):
        try:
            result = check_and_install_update(self.signals.progress.emit)
        except Exception as exc:  # defensive: worker must never kill Qt's pool
            result = {"state": "failed", "last_result": f"Update check failed: {exc}"}
        self.signals.finished.emit(result)


def bootstrap_ytdlp(status_callback=None) -> dict:
    """Backward-compatible local bootstrap with no network on the startup path."""
    return warm_ytdlp_runtime(prepare_ytdlp_runtime())


def get_runtime_status() -> dict:
    return dict(_STATUS)
