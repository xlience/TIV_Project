"""Main entry point: EVO telemetry -> Motion Engine -> virtual command monitor.

Software-only: no network transmission or hardware control is implemented.
Run from this folder with: python main.py
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from math import degrees

import argparse
import ctypes
import sys

from motion import MotionController
from sources import GAMES, create_reader

# Capture keeps polling EVO rapidly; the motion loop runs at a stable target rate.
CAPTURE_HZ = 333
MOTION_HZ = 100
PRINT_INTERVAL_S = 1.0
STALE_TIMEOUT_S = 0.25  # no new frame for this long -> neutral + reset


async def main(game: str, swap_yz: bool = False) -> None:
    reader = create_reader(game, CAPTURE_HZ, swap_yz)
    motion_controller = MotionController()

    period = 1.0 / MOTION_HZ
    print("=" * 72)
    print("  3DOF MOTION SOFTWARE — TELEMETRY + VIRTUAL COMMAND MONITOR")
    print("=" * 72)
    print(f"Source: {game}")
    print(f"Requested capture polling: {CAPTURE_HZ} Hz")
    print(f"Motion engine target: {MOTION_HZ} Hz ({period * 1000:.2f} ms)")
    print("Mode: SOFTWARE ONLY — no ESP32 or actuator output")
    print("Start EVO and drive. Press Ctrl+C to stop.")
    print()

    started = False
    loop_deadline = time.perf_counter()
    previous_loop_start: float | None = None
    last_sample_time: float | None = None
    last_print_time = time.perf_counter()
    last_motion = None
    last_command = None
    samples = 0
    loop_intervals: list[float] = []
    reader_costs: list[float] = []
    late_cycles = 0
    missed_frames = 0

    try:
        await reader.start()
        started = True
        while True:
            loop_start = time.perf_counter()
            if previous_loop_start is not None:
                loop_intervals.append(loop_start - previous_loop_start)
                if len(loop_intervals) > MOTION_HZ * 5:
                    del loop_intervals[:-MOTION_HZ * 5]
            previous_loop_start = loop_start

            read_start = time.perf_counter()
            vehicle = reader.get_latest()
            reader_costs.append(time.perf_counter() - read_start)
            if len(reader_costs) > MOTION_HZ * 5:
                del reader_costs[:-MOTION_HZ * 5]

            if vehicle is not None:
                sample_now = time.perf_counter()
                sample_dt = sample_now - last_sample_time if last_sample_time is not None else period
                last_sample_time = sample_now
                last_motion = vehicle
                last_command = motion_controller.update(vehicle, sample_dt)
                samples += 1
            else:
                missed_frames += 1
                if (last_sample_time is not None and last_command is not None
                        and last_command.valid
                        and time.perf_counter() - last_sample_time > STALE_TIMEOUT_S):
                    # Telemetry stopped (pause, menu, game closed): do not hold
                    # the last motion; reset to neutral until frames resume.
                    motion_controller.reset()
                    last_command = replace(
                        last_command, pitch_deg=0.0, roll_deg=0.0,
                        heave_norm=0.0, valid=False)
                    last_sample_time = None

            now = time.perf_counter()
            if now - last_print_time >= PRINT_INTERVAL_S:
                if loop_intervals:
                    avg_dt = sum(loop_intervals) / len(loop_intervals)
                    loop_hz = 1.0 / avg_dt if avg_dt > 0 else 0.0
                    max_dt = max(loop_intervals)
                else:
                    avg_dt = max_dt = 0.0
                    loop_hz = 0.0
                avg_read_ms = (
                    1000 * sum(reader_costs) / len(reader_costs) if reader_costs else 0.0
                )
                print()
                print(
                    f"Motion loop: {loop_hz:6.1f} Hz | "
                    f"mean {avg_dt * 1000:6.2f} ms | max {max_dt * 1000:6.2f} ms | "
                    f"get_latest avg {avg_read_ms:5.2f} ms"
                )
                if last_motion is None or last_command is None:
                    print("Telemetry: waiting for a valid EVO physics frame...")
                else:
                    fl, fr, rl, rr = last_motion.wheels
                    print(
                        f"Vehicle attitude: pitch {degrees(last_motion.pitch_rad):+7.3f}° | "
                        f"roll {degrees(last_motion.roll_rad):+7.3f}°"
                    )
                    print(
                        f"Acceleration: lat {last_motion.lateral_g:+6.3f} g | "
                        f"vert {last_motion.vertical_g:+6.3f} g | "
                        f"long {last_motion.longitudinal_g:+6.3f} g"
                    )
                    print(
                        f"Wheel load (N): FL {fl.load:7.1f} | FR {fr.load:7.1f} | "
                        f"RL {rl.load:7.1f} | RR {rr.load:7.1f}"
                    )
                    print(
                        f"Suspension (mm): FL {fl.suspension_travel*1000:6.1f} | "
                        f"FR {fr.suspension_travel*1000:6.1f} | "
                        f"RL {rl.suspension_travel*1000:6.1f} | "
                        f"RR {rr.suspension_travel*1000:6.1f}"
                    )
                    print(
                        "VIRTUAL MOTION COMMAND: "
                        f"Pitch {last_command.pitch_deg:+7.3f}° | "
                        f"Roll {last_command.roll_deg:+7.3f}° | "
                        f"Heave {last_command.heave_norm:+6.3f} (normalized)"
                    )
                    print(f"Samples processed: {samples} | Source: {last_motion.source}")
                print(
                    f"Scheduler: late cycles {late_cycles} | "
                    f"polls without a new frame {missed_frames}"
                )
                last_print_time = now

            # Deadline-based pacing avoids a busy loop and limits drift. If a
            # read takes too long, skip missed deadlines instead of spinning.
            loop_deadline += period
            after_work = time.perf_counter()
            if after_work > loop_deadline:
                late_cycles += 1
                if after_work - loop_deadline > period:
                    loop_deadline = after_work
            await asyncio.sleep(max(0.0, loop_deadline - time.perf_counter()))

    except asyncio.CancelledError:
        # asyncio.run cancels the main task during Ctrl+C on some Python versions.
        pass
    finally:
        if started:
            try:
                await reader.stop()
            except Exception as exc:
                print(f"Warning while stopping telemetry: {exc}")
        motion_controller.reset()
        print("\nTelemetry stopped. Virtual motion state reset.")


def _set_timer_resolution(on: bool) -> None:
    # Windows default timer tick is ~15.6 ms, which makes a 10 ms sleep jittery.
    if sys.platform == "win32":
        try:
            (ctypes.windll.winmm.timeBeginPeriod if on
             else ctypes.windll.winmm.timeEndPeriod)(1)
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", choices=GAMES, default="acevo")
    parser.add_argument("--swap-yz", action="store_true",
                        help="swap vertical/longitudinal acceleration axes")
    args = parser.parse_args()
    _set_timer_resolution(True)
    try:
        asyncio.run(main(args.game, args.swap_yz))
    except KeyboardInterrupt:
        # Fallback for Python/terminal combinations that deliver Ctrl+C outside
        # the coroutine cancellation path.
        print("\nStopped by user.")
    finally:
        _set_timer_resolution(False)
