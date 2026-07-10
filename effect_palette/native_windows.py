from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


IS_WINDOWS = os.name == "nt"
SW_RESTORE = 9
ERROR_ALREADY_EXISTS = 183
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


def _load_library(name: str):
    if not IS_WINDOWS:
        return None
    try:
        return ctypes.WinDLL(name, use_last_error=True)
    except Exception:
        return None


USER32 = _load_library("user32")
KERNEL32 = _load_library("kernel32")


def _configure_apis() -> None:
    if USER32 is not None:
        USER32.GetForegroundWindow.argtypes = []
        USER32.GetForegroundWindow.restype = wintypes.HWND
        USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        USER32.GetWindowTextLengthW.restype = ctypes.c_int
        USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        USER32.GetWindowTextW.restype = ctypes.c_int
        USER32.IsIconic.argtypes = [wintypes.HWND]
        USER32.IsIconic.restype = wintypes.BOOL
        USER32.IsWindow.argtypes = [wintypes.HWND]
        USER32.IsWindow.restype = wintypes.BOOL
        USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        USER32.ShowWindow.restype = wintypes.BOOL
        USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
        USER32.SetForegroundWindow.restype = wintypes.BOOL
        USER32.BringWindowToTop.argtypes = [wintypes.HWND]
        USER32.BringWindowToTop.restype = wintypes.BOOL
        USER32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        USER32.RegisterHotKey.restype = wintypes.BOOL
        USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        USER32.UnregisterHotKey.restype = wintypes.BOOL
        USER32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        USER32.GetMessageW.restype = wintypes.BOOL
        USER32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        USER32.PeekMessageW.restype = wintypes.BOOL
        USER32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        USER32.PostThreadMessageW.restype = wintypes.BOOL

    if KERNEL32 is not None:
        KERNEL32.GetCurrentThreadId.argtypes = []
        KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD
        KERNEL32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        KERNEL32.CreateMutexW.restype = wintypes.HANDLE
        KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
        KERNEL32.CloseHandle.restype = wintypes.BOOL


_configure_apis()


def foreground_window_handle() -> int | None:
    if USER32 is None:
        return None
    try:
        hwnd = USER32.GetForegroundWindow()
        return int(hwnd) if hwnd else None
    except Exception:
        return None


def foreground_window_title() -> str | None:
    if USER32 is None:
        return None
    try:
        hwnd = USER32.GetForegroundWindow()
        if not hwnd:
            return None
        length = USER32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        USER32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return None


def is_window(hwnd: int | None) -> bool:
    if not hwnd or USER32 is None:
        return False
    try:
        return bool(USER32.IsWindow(wintypes.HWND(hwnd)))
    except Exception:
        return False


def is_minimized(hwnd: int | None) -> bool:
    if not is_window(hwnd):
        return False
    try:
        return bool(USER32.IsIconic(wintypes.HWND(hwnd)))
    except Exception:
        return False


def activate_window(hwnd: int | None) -> bool:
    """Request foreground activation without altering a maximized window."""
    if not is_window(hwnd):
        return False
    native_hwnd = wintypes.HWND(hwnd)
    try:
        if USER32.IsIconic(native_hwnd):
            USER32.ShowWindow(native_hwnd, SW_RESTORE)
        USER32.BringWindowToTop(native_hwnd)
        return bool(USER32.SetForegroundWindow(native_hwnd))
    except Exception:
        return False


class SingleInstanceMutex:
    def __init__(self, name: str):
        self.name = name
        self.handle = None
        self.already_running = False

    def acquire(self) -> bool:
        if KERNEL32 is None:
            return True
        ctypes.set_last_error(0)
        handle = KERNEL32.CreateMutexW(None, False, self.name)
        if not handle:
            return False
        self.handle = handle
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if self.already_running:
            self.release()
            return False
        return True

    def release(self) -> None:
        if self.handle is None or KERNEL32 is None:
            return
        try:
            KERNEL32.CloseHandle(self.handle)
        finally:
            self.handle = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("FX.palette is already running")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
