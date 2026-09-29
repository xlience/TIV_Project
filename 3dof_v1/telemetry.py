from dataclasses import dataclass

from acevo import TelemetryCapture


@dataclass
class VehicleMotion:
    """
    Motion data received from Assetto Corsa EVO.
    """

    pitch_rad: float
    roll_rad: float

    lateral_g: float
    vertical_g: float
    longitudinal_g: float


class TelemetryReader:
    """
    Reads only the data required by the motion system.
    """

    def __init__(self, hz=60):
        self.capture = TelemetryCapture(hz=hz)

    async def start(self):
        await self.capture.start_capture()

    async def stop(self):
        await self.capture.stop_capture()

    def get_motion(self):
        frames = self.capture.get_frames()

        if not frames:
            return None

        physics = frames[-1].physics

        acc_g = physics.get("acc_g") or {}

        pitch_rad = physics.get("pitch") or 0.0
        roll_rad = physics.get("roll") or 0.0

        # EVO acceleration axes
        lateral_g = acc_g.get("x") or 0.0
        vertical_g = acc_g.get("y") or 0.0
        longitudinal_g = acc_g.get("z") or 0.0

        return VehicleMotion(
            pitch_rad=pitch_rad,
            roll_rad=roll_rad,
            lateral_g=lateral_g,
            vertical_g=vertical_g,
            longitudinal_g=longitudinal_g,
        )