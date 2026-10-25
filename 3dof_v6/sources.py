"""Game selection: one place that maps a game name to its telemetry adapter."""
from __future__ import annotations

from telemetry import AxisMap

GAMES = ("auto", "acevo", "ac", "acc", "lmu")


def create_reader(game: str, hz: int = 333, swap_yz: bool = False):
    game = game.lower()
    if game == "auto":
        raise ValueError("'auto' must be resolved with detect.auto_select() first.")
    axes = AxisMap().swap_yz() if swap_yz else AxisMap()
    if game == "acevo":
        from telemetry import EvoTelemetryReader
        return EvoTelemetryReader(hz=hz, axes=axes)
    if game in ("ac", "acc"):
        from telemetry_ac import AcSharedMemoryReader
        return AcSharedMemoryReader(source_name=game, axes=axes)
    if game == "lmu":
        from telemetry_lmu import LmuSharedMemoryReader
        return LmuSharedMemoryReader(axes=None if not swap_yz else
                                     AxisMap(longitudinal_sign=-1.0).swap_yz())
    raise ValueError(f"Unknown game '{game}'. Available: {', '.join(GAMES)}")
