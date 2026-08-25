"""Minimal Windows taskbar progress support (ITaskbarList3) using only the stdlib.

Every method degrades silently to a no-op when COM or the platform does not
cooperate, so callers never need to guard their calls.
"""
import ctypes
import sys


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _make_guid(data1: int, data2: int, data3: int, tail_hex: str) -> _GUID:
    guid = _GUID()
    guid.Data1 = data1
    guid.Data2 = data2
    guid.Data3 = data3
    for i in range(8):
        guid.Data4[i] = int(tail_hex[i * 2:(i * 2) + 2], 16)
    return guid


_CLSID_TASKBARLIST = _make_guid(0x56FDF344, 0xFD6D, 0x11D0, "958A006097C9A090")
_IID_ITASKBARLIST3 = _make_guid(0xEA1AFB91, 0x9E28, 0x4B86, "90E99E9F8A5EEFAF")

_CLSCTX_INPROC_SERVER = 1

# ITaskbarList3 progress state flags
TBPF_NOPROGRESS = 0x00000000
TBPF_INDETERMINATE = 0x00000001
TBPF_NORMAL = 0x00000002

# Vtable prototypes (index follows ITaskbarList -> ITaskbarList2 -> ITaskbarList3 order)
_HR_INIT_PROTO = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)                                    # idx 3
_SET_STATE_PROTO = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p)  # idx 8
_SET_VALUE_PROTO = ctypes.WINFUNCTYPE(
    ctypes.HRESULT, ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_ulonglong                             # idx 9
)


class WinTaskbarProgress:
    """Green download-progress overlay on the Windows taskbar button."""

    def __init__(self):
        self._window = None
        self._taskbar = None
        self._hwnd = 0
        self._ready = False
        self._failed = sys.platform != "win32"

    def attach(self, window):
        """Binds the progress overlay to a shown/soon-shown top-level window."""
        self._window = window

    def _ensure_ready(self) -> bool:
        if self._ready or self._failed:
            return self._ready
        try:
            self._hwnd = int(self._window.winId())
            handle = ctypes.c_void_p()
            ctypes.oledll.ole32.CoCreateInstance(
                ctypes.byref(_CLSID_TASKBARLIST), None, _CLSCTX_INPROC_SERVER,
                ctypes.byref(_IID_ITASKBARLIST3), ctypes.byref(handle),
            )
            if not handle:
                raise OSError("CoCreateInstance returned a null taskbar pointer")
            self._taskbar = handle
            # HrInit must run before any other taskbar call
            self._method(3, _HR_INIT_PROTO)(handle)
            self._ready = True
        except Exception:
            self._failed = True
        return self._ready

    def _method(self, index: int, prototype):
        iface_ptr = ctypes.c_void_p(self._taskbar)
        vtable_pp = ctypes.cast(ctypes.byref(iface_ptr), ctypes.POINTER(ctypes.c_void_p))
        vtable = ctypes.cast(vtable_pp[0], ctypes.POINTER(ctypes.c_void_p))
        return prototype(vtable[index])

    def set_progress(self, done: int, total: int = 100):
        if total <= 0 or not self._ensure_ready():
            return
        try:
            clamped = min(max(0, int(done)), int(total))
            self._method(8, _SET_STATE_PROTO)(self._taskbar, TBPF_NORMAL, self._hwnd)
            self._method(9, _SET_VALUE_PROTO)(self._taskbar, self._hwnd, clamped, int(total))
        except Exception:
            self._failed = True

    def clear(self):
        if not self._ready:
            return
        try:
            self._method(8, _SET_STATE_PROTO)(self._taskbar, TBPF_NOPROGRESS, self._hwnd)
        except Exception:
            self._failed = True
