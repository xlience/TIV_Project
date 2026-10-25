"""Le Mans Ultimate adapter: reads the game's built-in `LMU_Data` shared memory.

Layout facts (LMU interface, 4-byte packing; see pyLMUSharedMemory docs):
  root = generic(332) + paths(1300) + scoring(126832) + telemetry(196356)
  telemetry = activeVehicles(u8) playerVehicleIdx(u8) playerHasVehicle(bool) +pad
              then telemInfo[104], 1888 bytes each.
Only the player's record is copied each poll (not the whole 324 KB).
Telemetry is published at ~100 Hz (measured by probe_lmu.py: 100.4/s).

Axes (rF2 convention, to be verified in-game like for the other games):
  local accel x = left, y = up, z = rearward. So lateral = +x, vertical = +y,
  longitudinal = -z. Right turn must give negative lateral, braking negative
  longitudinal (same convention as AC/ACC/EVO).
"""
from __future__ import annotations

import ctypes
import time
from typing import Callable

from telemetry import AxisMap, VehicleMotion, WheelMotion, _number

G = 9.80665
ROOT_SIZE = 324_820
GAME_VERSION_OFFSET = 64                   # generic.events is 16 * 4 bytes
TELEMETRY_OFFSET = 332 + 1300 + 126_832    # 128464
VEHICLE_SIZE = 1888
MAX_VEHICLES = 104


class _Wheel(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mSuspensionDeflection", ctypes.c_double),  # offset 0, metres
        ("_pad0", ctypes.c_ubyte * 96),
        ("mTireLoad", ctypes.c_double),               # offset 104, newtons
        ("_pad1", ctypes.c_ubyte * 148),
    ]


class _Vector3(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("z", ctypes.c_double)]


class _Vehicle(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mID", ctypes.c_int32),
        ("mDeltaTime", ctypes.c_double),
        ("mElapsedTime", ctypes.c_double),
        ("_pad0", ctypes.c_ubyte * (208 - 20)),
        ("mLocalAccel", _Vector3),                    # offset 208, m/s^2
        ("_pad1", ctypes.c_ubyte * (848 - 232)),
        ("mWheels", _Wheel * 4),                      # offset 848: FL FR RL RR
    ]


class _TelemetryHead(ctypes.Structure):
    _pack_ = 4
    _fields_ = [("activeVehicles", ctypes.c_uint8),
                ("playerVehicleIdx", ctypes.c_uint8),
                ("playerHasVehicle", ctypes.c_bool)]


Opener = Callable[[], "object | None"]


def _windows_opener() -> object | None:
    from winshm import open_existing
    view = open_existing("LMU_Data", ROOT_SIZE)
    return view.buffer if view else None


class LmuSharedMemoryReader:
    """Poll LMU_Data; returns each new player telemetry record once."""

    source_name = "lmu"
    RETRY_OPEN_S = 1.0

    def __init__(self, axes: AxisMap | None = None, opener: Opener | None = None):
        self.axes = axes or AxisMap(longitudinal_sign=-1.0)
        self._opener = opener or _windows_opener
        self._buffer = None
        self._last_elapsed: float | None = None
        self._last_open_try = 0.0
        self._last_receive = 0.0

    async def start(self) -> None:
        self._try_open()

    async def stop(self) -> None:
        self._buffer = None

    def _try_open(self) -> None:
        self._last_open_try = time.perf_counter()
        self._buffer = self._opener()

    def game_ready(self) -> bool:
        """True when LMU is running and a player car exists (used by auto-detect)."""
        if self._buffer is None:
            self._try_open()
        if self._buffer is None:
            return False
        version = ctypes.c_int32.from_buffer_copy(self._buffer, GAME_VERSION_OFFSET).value
        head = _TelemetryHead.from_buffer_copy(self._buffer, TELEMETRY_OFFSET)
        return version != 0 and head.playerHasVehicle

    def get_latest(self) -> VehicleMotion | None:
        if self._buffer is None:
            if time.perf_counter() - self._last_open_try < self.RETRY_OPEN_S:
                return None
            self._try_open()
            if self._buffer is None:
                return None

        head = _TelemetryHead.from_buffer_copy(self._buffer, TELEMETRY_OFFSET)
        index = head.playerVehicleIdx
        if not head.playerHasVehicle or index >= min(head.activeVehicles, MAX_VEHICLES):
            return None
        offset = TELEMETRY_OFFSET + 4 + index * VEHICLE_SIZE
        v = _Vehicle.from_buffer_copy(self._buffer, offset)
        if v.mElapsedTime == self._last_elapsed:
            return None
        self._last_elapsed = v.mElapsedTime

        now = time.perf_counter()
        if now <= self._last_receive:
            now = self._last_receive + 1e-9
        self._last_receive = now

        a = (_number(v.mLocalAccel.x) / G, _number(v.mLocalAccel.y) / G,
             _number(v.mLocalAccel.z) / G)
        ax = self.axes
        wheels = tuple(
            WheelMotion(load=max(0.0, _number(w.mTireLoad)),
                        suspension_travel=_number(w.mSuspensionDeflection))
            for w in v.mWheels
        )
        return VehicleMotion(
            timestamp=now,
            pitch_rad=0.0,  # not derived; Motion Engine ignores attitude (gain 0)
            roll_rad=0.0,
            lateral_g=a[ax.lateral_index] * ax.lateral_sign,
            vertical_g=a[ax.vertical_index] * ax.vertical_sign,
            longitudinal_g=a[ax.longitudinal_index] * ax.longitudinal_sign,
            wheels=wheels,  # type: ignore[arg-type]
            source="lmu",
            session_active=True,
        )
