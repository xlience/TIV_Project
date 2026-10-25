"""Background motion engine for the GUI: telemetry -> MotionController -> snapshot.

Runs in its own thread with its own asyncio loop. The GUI only calls
start()/stop()/set_config()/start_test()/snapshot(); it never touches telemetry.
Software only: no hardware output.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, replace
from math import pi, sin

from motion import MotionCommand, MotionConfig, MotionController
from telemetry import VehicleMotion

STALE_TIMEOUT_S = 0.25
TEST_DURATION_S = 12.0
CAPTURE_HZ = 333


@dataclass(frozen=True)
class Snapshot:
    state: str = "idle"            # idle|waiting|connected|stale|test|error
    game: str = ""
    message: str = ""
    vehicle: VehicleMotion | None = None
    command: MotionCommand | None = None
    loop_hz: float = 0.0
    max_ms: float = 0.0
    samples: int = 0
    missed: int = 0


def test_pattern(t: float) -> tuple[float, float, float]:
    """Virtual movement sweep: pitch, then roll, then heave, then all together.

    Returns (pitch_deg, roll_deg, heave_norm) for time t in seconds. Amplitudes
    are a fraction of a typical software limit; the result is clamped by the caller.
    """
    s = sin(2 * pi * t / 3.0)
    if t < 3.0:
        return 6.0 * s, 0.0, 0.0
    if t < 6.0:
        return 0.0, 6.0 * s, 0.0
    if t < 9.0:
        return 0.0, 0.0, 0.8 * s
    return 4.0 * s, 4.0 * sin(2 * pi * t / 2.0), 0.4 * s


class MotionRunner:
    def __init__(self, reader_factory=None, controller: MotionController | None = None):
        self._reader_factory = reader_factory
        self._controller = controller or MotionController()
        self._lock = threading.Lock()
        self._snap = Snapshot()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

    # ---- GUI-facing API -------------------------------------------------
    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snap

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_config(self, config: MotionConfig) -> None:
        self._controller.config = config  # plain attribute swap, applied next update

    def start(self, game: str, loop_hz: int, swap_yz: bool = False) -> None:
        self._launch(self._run_game(game, loop_hz, swap_yz))

    def start_test(self, loop_hz: int = 100) -> None:
        self._launch(self._run_test(loop_hz))

    def stop(self) -> None:
        loop, task, thread = self._loop, self._task, self._thread
        if loop and task and not task.done():
            loop.call_soon_threadsafe(task.cancel)
        if thread:
            thread.join(timeout=3.0)
        self._thread = None
        self._set(Snapshot(state="idle"))

    # ---- internals ------------------------------------------------------
    def _set(self, snap: Snapshot) -> None:
        with self._lock:
            self._snap = snap

    def _launch(self, coro) -> None:
        if self.is_running():
            coro.close()
            return
        started = threading.Event()

        def target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._task = loop.create_task(coro)
            started.set()
            try:
                loop.run_until_complete(self._task)
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # surface to the GUI instead of dying silently
                self._set(Snapshot(state="error", message=f"{type(exc).__name__}: {exc}"))
            finally:
                loop.close()

        self._controller.reset()
        self._thread = threading.Thread(target=target, name="motion-engine", daemon=True)
        self._thread.start()
        started.wait(timeout=2.0)

    @staticmethod
    async def _pace(deadline: float) -> None:
        remaining = deadline - time.perf_counter()
        if remaining > 0.002:
            await asyncio.sleep(remaining - 0.0015)
        while time.perf_counter() < deadline:
            await asyncio.sleep(0)  # yield so reader tasks keep running

    async def _run_test(self, loop_hz: int) -> None:
        period = 1.0 / loop_hz
        t0 = time.perf_counter()
        deadline = t0
        cfg_clamp = lambda v, lim: max(-lim, min(lim, v))
        while True:
            t = time.perf_counter() - t0
            if t > TEST_DURATION_S:
                break
            c = self._controller.config
            p, r, h = test_pattern(t)
            cmd = MotionCommand(cfg_clamp(p, c.max_pitch_deg), cfg_clamp(r, c.max_roll_deg),
                                cfg_clamp(h, c.max_heave_norm), time.perf_counter(), "test", True)
            self._set(Snapshot(state="test", game="test", command=cmd, loop_hz=loop_hz))
            deadline += period
            await self._pace(deadline)
        self._set(Snapshot(state="idle", message="Тест движения завершён"))

    async def _run_game(self, game: str, loop_hz: int, swap_yz: bool) -> None:
        if game == "auto":
            self._set(Snapshot(state="waiting", game="auto"))
            from detect import auto_select

            def ask(found):
                raise RuntimeError("Запущено несколько игр (" + ", ".join(found) +
                                   "). Закройте лишние или выберите игру вручную.")
            game = await auto_select(ask=ask, announce=lambda *_: None)
            if game is None:
                return
        factory = self._reader_factory
        if factory is None:
            from sources import create_reader as factory
        reader = factory(game, CAPTURE_HZ, swap_yz)

        period = 1.0 / loop_hz
        controller = self._controller
        deadline = time.perf_counter()
        prev_start: float | None = None
        last_sample: float | None = None
        vehicle = None
        command: MotionCommand | None = None
        intervals: list[float] = []
        samples = missed = 0
        state = "waiting"
        started = False
        try:
            await reader.start()
            started = True
            while True:
                now = time.perf_counter()
                if prev_start is not None:
                    intervals.append(now - prev_start)
                    del intervals[:-loop_hz * 3]
                prev_start = now

                frame = reader.get_latest()
                if frame is not None:
                    dt = now - last_sample if last_sample is not None else period
                    last_sample = now
                    vehicle = frame
                    command = controller.update(frame, dt)
                    samples += 1
                    state = "connected" if command.valid else "stale"
                else:
                    missed += 1
                    if (last_sample is not None and command is not None and command.valid
                            and now - last_sample > STALE_TIMEOUT_S):
                        controller.reset()
                        command = replace(command, pitch_deg=0.0, roll_deg=0.0,
                                          heave_norm=0.0, valid=False)
                        last_sample = None
                        state = "stale"

                hz = (len(intervals) / sum(intervals)) if intervals and sum(intervals) > 0 else 0.0
                self._set(Snapshot(state=state, game=game, vehicle=vehicle, command=command,
                                   loop_hz=hz, max_ms=1000 * max(intervals, default=0.0),
                                   samples=samples, missed=missed))
                deadline += period
                if time.perf_counter() - deadline > period:
                    deadline = time.perf_counter()
                await self._pace(deadline)
        finally:
            if started:
                try:
                    await reader.stop()
                except Exception:
                    pass
            controller.reset()
