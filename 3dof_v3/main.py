import asyncio
import time
from math import degrees

from telemetry import TelemetryReader


TARGET_HZ = 333
PRINT_INTERVAL = 1.0


async def main():
    reader = TelemetryReader(hz=TARGET_HZ)

    print("=" * 60)
    print("           EVO 3DOF TELEMETRY")
    print("=" * 60)
    print()
    print(f"Telemetry rate: {TARGET_HZ} Hz")
    print(f"Target period: {1000 / TARGET_HZ:.3f} ms")
    print()
    print("Start Assetto Corsa EVO and drive.")
    print("Ctrl+C — stop")
    print()

    await reader.start()

    last_loop = time.perf_counter()
    last_print = time.perf_counter()

    loop_times = []
    frames_received = 0

    try:
        while True:

            loop_start = time.perf_counter()

            motion = reader.get_latest()

            if motion is not None:

                frames_received += 1

                pitch_deg = degrees(motion.pitch_rad)
                roll_deg = degrees(motion.roll_rad)

                fl, fr, rl, rr = motion.wheels

                now = time.perf_counter()

                # ------------------------------------------
                # Loop timing
                # ------------------------------------------

                if last_loop is not None:
                    dt = now - last_loop

                    if dt > 0:
                        loop_times.append(dt)

                        if len(loop_times) > 333:
                            loop_times.pop(0)

                last_loop = now

                # ------------------------------------------
                # Print once per second
                # ------------------------------------------

                if now - last_print >= PRINT_INTERVAL:

                    if loop_times:
                        avg_dt = sum(loop_times) / len(loop_times)
                        actual_hz = 1.0 / avg_dt
                    else:
                        avg_dt = 0.0
                        actual_hz = 0.0

                    print()
                    print(
                        f"Loop: {actual_hz:6.1f} Hz | "
                        f"{avg_dt * 1000:6.3f} ms"
                    )

                    print(
                        f"Pitch: {pitch_deg:+7.3f}° | "
                        f"Roll: {roll_deg:+7.3f}°"
                    )

                    print(
                        f"G: "
                        f"Lat {motion.lateral_g:+6.3f} | "
                        f"Vert {motion.vertical_g:+6.3f} | "
                        f"Long {motion.longitudinal_g:+6.3f}"
                    )

                    print(
                        f"Load: "
                        f"FL {fl.load:7.1f} | "
                        f"FR {fr.load:7.1f} | "
                        f"RL {rl.load:7.1f} | "
                        f"RR {rr.load:7.1f}"
                    )

                    print(
                        f"Susp: "
                        f"FL {fl.suspension_travel * 1000:6.1f} mm | "
                        f"FR {fr.suspension_travel * 1000:6.1f} mm | "
                        f"RL {rl.suspension_travel * 1000:6.1f} mm | "
                        f"RR {rr.suspension_travel * 1000:6.1f} mm"
                    )

                    print(
                        f"Frames received: {frames_received}"
                    )

                    last_print = now

            # ----------------------------------------------
            # Yield to asyncio
            # ----------------------------------------------

            await asyncio.sleep(0)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print()
        print("Stopping...")

    finally:
        await reader.stop()
        print("Telemetry stopped.")


if __name__ == "__main__":
    asyncio.run(main())