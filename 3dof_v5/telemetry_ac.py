"""Assetto Corsa (AC) and Assetto Corsa Competizione (ACC) shared-memory adapter.

Both games expose the same leading part of the physics page, so one adapter
serves both; only the source name differs. Only the fields the Motion Engine
needs are mapped (everything up to `roll`); the rest of the page is ignored.

Windows only. Axis order and signs are configurable in AxisMap because they
must be validated in-game (see README: sign check procedure).
"""
from __future__ import annotations

import ctypes
import mmap
import sys
import time
from dataclasses import dataclass
from typing import Callable

from telemetry import AxisMap, VehicleMotion, WheelMotion, _number

STATUS_LIVE = 2  # graphics.status: 0 OFF, 1 REPLAY, 2 LIVE, 3 PAUSE


class _PhysicsHead(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int32),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int32),
        ("rpms", ctypes.c_int32),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("accG", ctypes.c_float * 3),
        ("wheelSlip", ctypes.c_float * 4),
        ("wheelLoad", ctypes.c_float * 4),
        ("wheelsPressure", ctypes.c_float * 4),
        ("wheelAngularSpeed", ctypes.c_float * 4),
        ("tyreWear", ctypes.c_float * 4),
        ("tyreDirtyLevel", ctypes.c_float * 4),
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD", ctypes.c_float * 4),
        ("suspensionTravel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
    ]


class _GraphicsHead(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("packetId", ctypes.c_int32), ("status", ctypes.c_int32)]


Opener = Callable[[str], "object | None"]


def _windows_opener(kind: str) -> object | None:
    """Open acpmf_<kind>; None if the game has not created it yet."""
    if sys.platform != "win32":
        raise RuntimeError("AC/ACC shared memory is only available on Windows.")
    size = ctypes.sizeof(_PhysicsHead if kind == "physics" else _GraphicsHead)
    for tag in (f"Local\\acpmf_{kind}", f"acpmf_{kind}"):
        try:
            return mmap.mmap(-1, size, tag, access=mmap.ACCESS_READ)
        except OSError:
            continue
    return None


class AcSharedMemoryReader:
    """Poll AC/ACC shared memory; returns each new physics packet once."""

    RETRY_OPEN_S = 1.0

    def __init__(self, source_name: str = "ac", axes: AxisMap | None = None,
                 opener: Opener | None = None):
        self.source_name = source_name
        self.axes = axes or AxisMap()
        self._opener = opener or _windows_opener
        self._physics = None
        self._graphics = None
        self._last_packet: int | None = None
        self._last_open_try = 0.0
        self._last_receive = 0.0

    async def start(self) -> None:
        self._try_open()

    async def stop(self) -> None:
        for page in (self._physics, self._graphics):
            close = getattr(page, "close", None)
            if close:
                close()
        self._physics = self._graphics = None

    def _try_open(self) -> None:
        self._last_open_try = time.perf_counter()
        if self._physics is None:
            self._physics = self._opener("physics")
        if self._graphics is None:
            self._graphics = self._opener("graphics")

    def get_latest(self) -> VehicleMotion | None:
        if self._physics is None:
            if time.perf_counter() - self._last_open_try >= self.RETRY_OPEN_S:
                self._try_open()
            if self._physics is None:
                return None  # game not running / session not created yet

        p = _PhysicsHead.from_buffer_copy(self._physics, 0)
        if p.packetId == self._last_packet:
            return None
        self._last_packet = p.packetId

        status = STATUS_LIVE
        if self._graphics is not None:
            status = _GraphicsHead.from_buffer_copy(self._graphics, 0).status

        a, ax = p.accG, self.axes
        now = time.perf_counter()
        if now <= self._last_receive:
            now = self._last_receive + 1e-9
        self._last_receive = now

        wheels = tuple(
            WheelMotion(load=max(0.0, _number(p.wheelLoad[i])),
                        suspension_travel=_number(p.suspensionTravel[i]))
            for i in range(4)
        )
        return VehicleMotion(
            timestamp=now,
            pitch_rad=_number(p.pitch) * ax.pitch_sign,
            roll_rad=_number(p.roll) * ax.roll_sign,
            lateral_g=_number(a[ax.lateral_index]) * ax.lateral_sign,
            vertical_g=_number(a[ax.vertical_index]) * ax.vertical_sign,
            longitudinal_g=_number(a[ax.longitudinal_index]) * ax.longitudinal_sign,
            wheels=wheels,  # type: ignore[arg-type]
            source=self.source_name,
            session_active=(status == STATUS_LIVE),
        )
