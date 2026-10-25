"""Telemetry input and normalized vehicle-motion model.

Implemented source: Assetto Corsa EVO via acevo-sdk.
Future game adapters should return the same VehicleMotion model; game-specific
parsing belongs in the adapter, not in motion.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Protocol


@dataclass(frozen=True)
class WheelMotion:
    """Per-wheel values in SI units: load in N, suspension travel in m."""
    load: float = 0.0
    suspension_travel: float = 0.0


@dataclass(frozen=True)
class VehicleMotion:
    """Normalized motion input shared by all game adapters.

    Angles: radians. Acceleration: g units. Wheel load: N.
    Suspension travel: metres. Wheel order: FL, FR, RL, RR.
    timestamp uses a monotonic clock in this adapter.
    """
    timestamp: float
    pitch_rad: float
    roll_rad: float
    lateral_g: float
    vertical_g: float
    longitudinal_g: float
    wheels: tuple[WheelMotion, WheelMotion, WheelMotion, WheelMotion]
    source: str = "acevo"
    session_active: bool = True


class TelemetrySource(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def get_latest(self) -> VehicleMotion | None: ...


def _number(value: object, default: float = 0.0) -> float:
    """Convert a value to a finite float; reject None/NaN/inf."""
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _as_list(value: object, count: int = 4) -> list[object]:
    """Safely normalize SDK array-like values to a fixed-length list."""
    if value is None or isinstance(value, (str, bytes, dict)):
        values: list[object] = []
    else:
        try:
            values = list(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            values = []
    values = values[:count]
    values.extend([0.0] * (count - len(values)))
    return values


class EvoTelemetryReader:
    """Read the newest available physics frame from Assetto Corsa EVO."""

    source_name = "acevo"

    def __init__(self, hz: int = 333):
        try:
            from acevo import TelemetryCapture
        except ImportError as exc:
            raise RuntimeError(
                "The 'acevo-sdk' package is required for Assetto Corsa EVO telemetry. "
                "Install it in the same Python environment used to run main.py."
            ) from exc
        self.capture = TelemetryCapture(hz=hz)
        self._last_frame_marker: object | None = None
        self._last_receive_timestamp = 0.0

    async def start(self) -> None:
        await self.capture.start_capture()

    async def stop(self) -> None:
        await self.capture.stop_capture()

    def get_latest(self) -> VehicleMotion | None:
        # Current public SDK interface returns a collection; consume only its
        # newest item. Avoid retaining or processing a backlog in this adapter.
        frames = self.capture.get_frames()
        if not frames:
            return None

        frame = frames[-1]
        frame_timestamp = getattr(frame, "timestamp", None)
        marker = frame_timestamp if frame_timestamp is not None else id(frame)
        if marker == self._last_frame_marker:
            return None
        self._last_frame_marker = marker

        physics = getattr(frame, "physics", None)
        if not isinstance(physics, dict):
            return None

        acc_g = physics.get("acc_g")
        if not isinstance(acc_g, dict):
            acc_g = {}

        loads = _as_list(physics.get("wheel_load"))
        travel = _as_list(physics.get("suspension_travel"))
        wheels = tuple(
            WheelMotion(
                load=max(0.0, _number(loads[i])),
                suspension_travel=_number(travel[i]),
            )
            for i in range(4)
        )

        # Do not assume SDK timestamp units. A monotonic local timestamp keeps
        # dt semantics consistent across adapters and avoids mixing clock domains.
        receive_timestamp = time.perf_counter()
        if receive_timestamp <= self._last_receive_timestamp:
            receive_timestamp = self._last_receive_timestamp + 1e-9
        self._last_receive_timestamp = receive_timestamp

        return VehicleMotion(
            timestamp=receive_timestamp,
            pitch_rad=_number(physics.get("pitch")),
            roll_rad=_number(physics.get("roll")),
            lateral_g=_number(acc_g.get("x")),
            vertical_g=_number(acc_g.get("y")),
            longitudinal_g=_number(acc_g.get("z")),
            wheels=wheels,  # type: ignore[arg-type]
            source=self.source_name,
        )


# Keep the established import name working.
TelemetryReader = EvoTelemetryReader
