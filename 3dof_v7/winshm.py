"""Read-only access to EXISTING Windows shared memory, never creating it.

Why not mmap.mmap(-1, size, tag)? That call CREATES a mapping when the game is
not running yet. Our empty read-only mapping would then block the game from
publishing its own data when it starts. OpenFileMapping only opens an existing
mapping and returns None otherwise.
"""
from __future__ import annotations

import ctypes
import sys

FILE_MAP_READ = 0x0004


class SharedView:
    """A mapped read-only view; `buffer` supports ctypes from_buffer_copy."""

    def __init__(self, handle, pointer, size):
        self._handle, self._pointer, self.size = handle, pointer, size
        self.buffer = (ctypes.c_char * size).from_address(pointer)

    def close(self) -> None:
        if self._pointer:
            ctypes.windll.kernel32.UnmapViewOfFile(ctypes.c_void_p(self._pointer))
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._handle))
            self._pointer = self._handle = 0
            self.buffer = None


def open_existing(name: str, size: int) -> SharedView | None:
    """Return a view of the first `size` bytes of an existing mapping, or None."""
    if sys.platform != "win32":
        raise RuntimeError("Shared memory readers are only available on Windows.")
    k32 = ctypes.windll.kernel32
    k32.OpenFileMappingW.restype = ctypes.c_void_p
    k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_uint32, ctypes.c_size_t]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    for candidate in (name, "Local\\" + name):
        handle = k32.OpenFileMappingW(FILE_MAP_READ, False, candidate)
        if not handle:
            continue
        pointer = k32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, size)
        if pointer:
            return SharedView(handle, pointer, size)
        k32.CloseHandle(ctypes.c_void_p(handle))
    return None
