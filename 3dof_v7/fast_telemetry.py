"""Standalone EVO capture-rate diagnostic; not used by main.py."""
from __future__ import annotations

import asyncio
import time

from acevo import TelemetryCapture

TARGET_HZ = 333


async def main() -> None:
    capture = TelemetryCapture(hz=TARGET_HZ)
    print("=" * 60)
    print("EVO TELEMETRY CHANGE-INTERVAL TEST")
    print("=" * 60)
    print(f"Requested polling rate: {TARGET_HZ} Hz")
    print(f"Nominal period: {1000 / TARGET_HZ:.3f} ms")
    print("Start Assetto Corsa EVO and drive. Ctrl+C to stop.")

    await capture.start_capture()
    last_signature = None
    last_change_time = None
    intervals: list[float] = []
    last_report = time.perf_counter()
    last_read_costs: list[float] = []

    try:
        while True:
            read_start = time.perf_counter()
            frames = capture.get_frames()
            last_read_costs.append(time.perf_counter() - read_start)
            if len(last_read_costs) > TARGET_HZ * 5:
                del last_read_costs[:-TARGET_HZ * 5]

            if frames:
                frame = frames[-1]
                physics = getattr(frame, "physics", None)
                if isinstance(physics, dict):
                    acc_g = physics.get("acc_g")
                    if not isinstance(acc_g, dict):
                        acc_g = {}
                    signature = (
                        physics.get("pitch"),
                        physics.get("roll"),
                        acc_g.get("x"),
                        acc_g.get("y"),
                        acc_g.get("z"),
                    )
                    now = time.perf_counter()
                    if signature != last_signature:
                        if last_change_time is not None:
                            dt = now - last_change_time
                            if dt > 0:
                                intervals.append(dt)
                        last_change_time = now
                        last_signature = signature

                    if now - last_report >= 1.0:
                        recent = intervals[-200:]
                        avg_read_ms = (
                            1000 * sum(last_read_costs) / len(last_read_costs)
                            if last_read_costs else 0.0
                        )
                        if recent:
                            avg_dt = sum(recent) / len(recent)
                            print(
                                f"Changed-data rate: {1 / avg_dt:7.1f} Hz | "
                                f"mean {avg_dt*1000:6.3f} ms | "
                                f"min {min(recent)*1000:6.3f} ms | "
                                f"max {max(recent)*1000:6.3f} ms | "
                                f"get_frames avg {avg_read_ms:5.2f} ms"
                            )
                        else:
                            print(f"Waiting for changing physics values... | get_frames avg {avg_read_ms:.2f} ms")
                        last_report = now
            await asyncio.sleep(0.001)
    except asyncio.CancelledError:
        pass
    finally:
        await capture.stop_capture()
        print("\nTelemetry stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
