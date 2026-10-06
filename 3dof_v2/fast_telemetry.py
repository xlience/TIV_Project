import asyncio
import time

from acevo import TelemetryCapture


TARGET_HZ = 333


async def main():
    capture = TelemetryCapture(hz=TARGET_HZ)

    print("=" * 60)
    print("        EVO TELEMETRY TIMING TEST")
    print("=" * 60)
    print()
    print(f"Requested polling rate: {TARGET_HZ} Hz")
    print(f"Target period: {1000 / TARGET_HZ:.3f} ms")
    print()
    print("Start Assetto Corsa EVO and drive.")
    print("Press Ctrl+C to stop.")
    print()

    await capture.start_capture()

    last_signature = None
    last_change_time = None

    intervals = []

    last_report = time.perf_counter()

    try:
        while True:

            frames = capture.get_frames()

            if frames:
                physics = frames[-1].physics

                # Берём несколько значений,
                # которые постоянно меняются во время движения.
                pitch = physics.get("pitch") or 0.0
                roll = physics.get("roll") or 0.0

                acc_g = physics.get("acc_g") or {}

                lateral_g = acc_g.get("x") or 0.0
                vertical_g = acc_g.get("y") or 0.0
                longitudinal_g = acc_g.get("z") or 0.0

                signature = (
                    pitch,
                    roll,
                    lateral_g,
                    vertical_g,
                    longitudinal_g,
                )

                now = time.perf_counter()

                if signature != last_signature:

                    if last_change_time is not None:
                        dt = now - last_change_time

                        if dt > 0:
                            intervals.append(dt)

                    last_change_time = now
                    last_signature = signature

                # Каждую секунду показываем статистику
                if now - last_report >= 1.0:

                    if intervals:
                        recent = intervals[-200:]

                        avg_dt = sum(recent) / len(recent)
                        measured_hz = 1.0 / avg_dt

                        min_dt = min(recent)
                        max_dt = max(recent)

                        print(
                            f"Measured: {measured_hz:7.1f} Hz | "
                            f"Period: {avg_dt * 1000:6.3f} ms | "
                            f"Min: {min_dt * 1000:6.3f} ms | "
                            f"Max: {max_dt * 1000:6.3f} ms"
                        )

                    last_report = now

            # Не используем жёсткий sleep 4 ms.
            # Пока просто отдаём управление event loop.
            await asyncio.sleep(0)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print()
        print("Stopping...")

    finally:
        await capture.stop_capture()

        print("Telemetry stopped.")


if __name__ == "__main__":
    asyncio.run(main())