import asyncio
import time

from telemetry import TelemetryReader
from motion import MotionController


CAPTURE_HZ = 60
DISPLAY_INTERVAL = 0.2


async def main():

    telemetry = TelemetryReader(
        hz=CAPTURE_HZ
    )

    motion_controller = MotionController()

    await telemetry.start()

    print()
    print("=" * 70)
    print("                 EVO 3DOF MOTION TEST")
    print("=" * 70)
    print()

    print("Wheel order:")
    print("  FL = Front Left")
    print("  FR = Front Right")
    print("  RL = Rear Left")
    print("  RR = Rear Right")
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

                    wheels = motion_data.wheels

                    print()
                    print(
                        f"Pitch: {command.pitch_deg:+7.2f}°   "
                        f"Roll: {command.roll_deg:+7.2f}°   "
                        f"Heave: {command.heave:+7.3f}"
                    )

                    print(
                        f"G: "
                        f"Lat {motion_data.lateral_g:+6.3f}   "
                        f"Vert {motion_data.vertical_g:+6.3f}   "
                        f"Long {motion_data.longitudinal_g:+6.3f}"
                    )

                    print(
                        "Load: "
                        f"FL {wheels[0].load:7.1f}  "
                        f"FR {wheels[1].load:7.1f}  "
                        f"RL {wheels[2].load:7.1f}  "
                        f"RR {wheels[3].load:7.1f}"
                    )

                    print(
                        "Susp: "
                        f"FL {wheels[0].suspension_travel:+7.4f}  "
                        f"FR {wheels[1].suspension_travel:+7.4f}  "
                        f"RL {wheels[2].suspension_travel:+7.4f}  "
                        f"RR {wheels[3].suspension_travel:+7.4f}"
                    )

                    last_display = now

            await asyncio.sleep(
                1 / CAPTURE_HZ
            )

    finally:

        await telemetry.stop()

        print()
        print("Motion controller stopped.")


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")