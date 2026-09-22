import asyncio
import time

from telemetry import TelemetryReader
from motion import MotionController


CAPTURE_HZ = 60
DISPLAY_INTERVAL = 0.1


async def main():

    telemetry = TelemetryReader(hz=CAPTURE_HZ)
    motion_controller = MotionController()

    await telemetry.start()

    print()
    print("=" * 60)
    print("              EVO MOTION CONTROLLER")
    print("=" * 60)
    print()
    print("EVO telemetry connected.")
    print("Motion system started.")
    print()
    print("Ctrl+C — остановить")
    print()

    last_display = 0.0

    try:

        while True:

            motion_data = telemetry.get_motion()

            if motion_data is not None:

                command = motion_controller.update(
                    motion_data
                )

                now = time.monotonic()

                if now - last_display >= DISPLAY_INTERVAL:

                    print(
                        f"\r"
                        f"Pitch: {command.pitch_deg:+6.2f}°   "
                        f"Roll: {command.roll_deg:+6.2f}°",
                        end="",
                        flush=True,
                    )

                    last_display = now

            await asyncio.sleep(1 / CAPTURE_HZ)

    finally:

        await telemetry.stop()

        print()
        print()
        print("Motion controller stopped.")


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")