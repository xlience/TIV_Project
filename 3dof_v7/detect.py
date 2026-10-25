"""Automatic game detection.

A game counts as 'running' only when telemetry is actually flowing, not merely
when its process or memory exists. If several games are running, the user is
asked to choose; the program never switches silently.

Detection never creates shared memory (see winshm.py).
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

PROBE_WINDOW_S = 0.4


def probe_ac_family(opener=None, window_s: float = PROBE_WINDOW_S) -> str | None:
    """Return 'ac' or 'acc' when the AC-style physics page is live, else None.

    Needs two distinct live packets (data really flowing). AC vs ACC: ACC does
    not fill wheel load (measured: always 0), AC does (measured: ~2000+ N).
    """
    from telemetry_ac import AcSharedMemoryReader
    reader = AcSharedMemoryReader(source_name="ac", opener=opener)
    reader.RETRY_OPEN_S = 0.0
    try:
        reader._try_open()
        frames = []
        end = time.perf_counter() + window_s
        while time.perf_counter() < end and len(frames) < 2:
            frame = reader.get_latest()
            if frame is not None and frame.session_active:
                frames.append(frame)
            else:
                time.sleep(0.003)
        if len(frames) < 2:
            return None
        return "ac" if sum(w.load for w in frames[0].wheels) > 0.0 else "acc"
    finally:
        for page in (reader._physics, reader._graphics):
            close = getattr(page, "close", None)
            if close:
                close()


def probe_lmu(opener=None) -> bool:
    from telemetry_lmu import LmuSharedMemoryReader
    reader = LmuSharedMemoryReader(opener=opener)
    return reader.game_ready()


async def probe_evo(window_s: float = 1.5) -> bool:
    """EVO has no cheap existence check here, so try a short capture."""
    try:
        from telemetry import EvoTelemetryReader
        reader = EvoTelemetryReader()
        await reader.start()
    except Exception:
        return False
    try:
        end = time.perf_counter() + window_s
        while time.perf_counter() < end:
            if reader.get_latest() is not None:
                return True
            await asyncio.sleep(0.02)
        return False
    finally:
        try:
            await reader.stop()
        except Exception:
            pass


async def find_running_games(include_evo: bool = True, *,
                             ac_probe: Callable[[], str | None] = probe_ac_family,
                             lmu_probe: Callable[[], bool] = probe_lmu,
                             evo_probe: Callable[[], Awaitable[bool]] = probe_evo) -> list[str]:
    found: list[str] = []
    if lmu_probe():
        found.append("lmu")
    ac_family = ac_probe()
    if ac_family:
        found.append(ac_family)
    if include_evo and await evo_probe():
        found.append("acevo")
    return found


def ask_user_to_choose(found: list[str]) -> str:
    print("Several games are sending telemetry:")
    for number, name in enumerate(found, 1):
        print(f"  {number}. {name}")
    while True:
        answer = input("Choose a number (or Ctrl+C to cancel): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(found):
            return found[int(answer) - 1]


async def auto_select(*, find=find_running_games, ask=ask_user_to_choose,
                      announce=print, poll_s: float = 1.0,
                      max_attempts: int | None = None) -> str | None:
    """Wait until exactly one game is live (or ask when several are)."""
    attempt = 0
    while max_attempts is None or attempt < max_attempts:
        found = await find(include_evo=(attempt % 3 == 0))
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            return ask(found)
        if attempt == 0:
            announce("No running game found. Start a game and sit in the car "
                     "on track (Ctrl+C to cancel)...")
        attempt += 1
        await asyncio.sleep(poll_s)
    return None
