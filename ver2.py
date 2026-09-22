import asyncio
from acevo import TelemetryCapture


def gear_name(gear: int) -> str:
    """
    EVO/AC gear encoding:
    0 = reverse
    1 = neutral
    2+ = gears
    """

    if gear == 0:
        return "R"

    if gear == 1:
        return "N"

    return str(gear - 1)


def get_value(data: dict, key: str, default=0.0):
    """Safely get a telemetry value and protect against None."""

    if not data:
        return default

    value = data.get(key, default)

    if value is None:
        return default

    return value


def print_telemetry(frame):
    physics = frame.physics
    graphics = frame.graphics

    if not physics:
        return

    speed = get_value(physics, "speed_kmh")
    rpm = get_value(physics, "rpms")
    gear = get_value(physics, "gear")

    throttle = get_value(physics, "gas")
    brake = get_value(physics, "brake")
    steering = get_value(physics, "steer_angle")

    fuel = get_value(physics, "fuel")

    acc_g = get_value(physics, "acc_g", None)

    if not isinstance(acc_g, dict):
        acc_g = {}

    gx = get_value(acc_g, "x", 0.0)
    gy = get_value(acc_g, "y", 0.0)
    gz = get_value(acc_g, "z", 0.0)

    pitch = get_value(physics, "pitch")
    roll = get_value(physics, "roll")
    heading = get_value(physics, "heading")

    print("\033[2J\033[H", end="")

    print("=" * 60)
    print("              ASSETTO CORSA EVO")
    print("                 TELEMETRY")
    print("=" * 60)

    print()

    print(f"Speed:       {speed:8.1f} km/h")
    print(f"RPM:         {rpm:8d}")
    print(f"Gear:        {gear_name(gear):>8}")

    print()

    print(f"Throttle:    {throttle * 100:8.1f} %")
    print(f"Brake:       {brake * 100:8.1f} %")
    print(f"Steering:    {steering:8.3f}")

    print()

    print("G-Force:")
    print(f"  X:         {gx:8.3f}")
    print(f"  Y:         {gy:8.3f}")
    print(f"  Z:         {gz:8.3f}")

    print()

    print("Car orientation:")
    print(f"  Pitch:     {pitch:8.3f}")
    print(f"  Roll:      {roll:8.3f}")
    print(f"  Heading:   {heading:8.3f}")

    print()

    print(f"Fuel:        {fuel:8.2f} L")

    # ---------------------------------------------------------
    # Graphics data
    # ---------------------------------------------------------

    if graphics:

        print()
        print("-" * 60)
        print("SESSION")

        lap = graphics.get("session_current_lap")
        lap_time = graphics.get("timing_current_laptime")
        position = graphics.get("current_pos")
        track_position = graphics.get("normalized_car_position")

        if lap is not None:
            print(f"Lap:         {lap}")

        if lap_time:
            print(f"Lap time:    {lap_time}")

        if position is not None:
            print(f"Position:    P{position}")

        if track_position is not None:
            print(f"Track pos:   {track_position:.4f}")

    print()
    print("=" * 60)
    print("Press Ctrl+C to stop")


async def main():

    capture = TelemetryCapture(hz=20)

    print("=" * 60)
    print("       ASSETTO CORSA EVO TELEMETRY TEST")
    print("=" * 60)

    print()
    print("Waiting for telemetry...")
    print("Start EVO and enter a session.")
    print()

    await capture.start_capture()

    try:

        while True:

            await asyncio.sleep(0.1)

            frames = capture.get_frames()

            if not frames:
                continue

            frame = frames[-1]

            print_telemetry(frame)

    finally:

        if capture.is_capturing():

            print()
            print("Stopping telemetry capture...")

            frames = await capture.stop_capture()

            print(f"Captured frames: {len(frames)}")


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("Telemetry stopped.")