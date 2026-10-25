"""Game selection: one place that maps a game name to its telemetry adapter."""
from __future__ import annotations

from telemetry import AxisMap

GAMES = ("acevo", "ac", "acc", "lmu")


def create_reader(game: str, hz: int = 333, swap_yz: bool = False):
    game = game.lower()
    axes = AxisMap().swap_yz() if swap_yz else AxisMap()
    if game == "acevo":
        from telemetry import EvoTelemetryReader
        return EvoTelemetryReader(hz=hz, axes=axes)
    if game in ("ac", "acc"):
        from telemetry_ac import AcSharedMemoryReader
        return AcSharedMemoryReader(source_name=game, axes=axes)
    if game == "lmu":
        raise NotImplementedError("LMU adapter is not implemented yet.")
    raise ValueError(f"Unknown game '{game}'. Available: {', '.join(GAMES)}")
