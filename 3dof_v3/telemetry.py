from dataclasses import dataclass
from acevo import TelemetryCapture


@dataclass
class WheelMotion:
    load: float
    suspension_travel: float


@dataclass
class VehicleMotion:
    timestamp: float

    pitch_rad: float
    roll_rad: float

    lateral_g: float
    vertical_g: float
    longitudinal_g: float

    wheels: tuple[
        WheelMotion,
        WheelMotion,
        WheelMotion,
        WheelMotion,
    ]


class TelemetryReader:
    """
    Reads the latest available physics frame from Assetto Corsa EVO.

    Internal units:
        angles           -> radians
        acceleration     -> g
        wheel load       -> Newtons
        suspension       -> meters
    """

    def __init__(self, hz=333):
        self.capture = TelemetryCapture(hz=hz)

    async def start(self):
        await self.capture.start_capture()

    async def stop(self):
        await self.capture.stop_capture()

    def get_latest(self):
        """
        Return the newest available physics frame.

        Old frames are intentionally ignored.
        """

        frames = self.capture.get_frames()

        if not frames:
            return None

        frame = frames[-1]
        physics = frame.physics

        # --------------------------------------------------
        # Body orientation
        # --------------------------------------------------

        pitch_rad = physics.get("pitch") or 0.0
        roll_rad = physics.get("roll") or 0.0

        # --------------------------------------------------
        # Acceleration
        #
        # EVO:
        # x = lateral
        # y = vertical
        # z = longitudinal
        # --------------------------------------------------

        acc_g = physics.get("acc_g") or {}

        lateral_g = acc_g.get("x") or 0.0
        vertical_g = acc_g.get("y") or 0.0
        longitudinal_g = acc_g.get("z") or 0.0

        # --------------------------------------------------
        # Wheel data
        #
        # Order:
        # FL, FR, RL, RR
        # --------------------------------------------------

        wheel_load = physics.get("wheel_load") or []
        suspension_travel = physics.get("suspension_travel") or []

        wheel_load = list(wheel_load)[:4]
        suspension_travel = list(suspension_travel)[:4]

        while len(wheel_load) < 4:
            wheel_load.append(0.0)

        while len(suspension_travel) < 4:
            suspension_travel.append(0.0)

        wheels = (
            WheelMotion(
                load=wheel_load[0],
                suspension_travel=suspension_travel[0],
            ),
            WheelMotion(
                load=wheel_load[1],
                suspension_travel=suspension_travel[1],
            ),
            WheelMotion(
                load=wheel_load[2],
                suspension_travel=suspension_travel[2],
            ),
            WheelMotion(
                load=wheel_load[3],
                suspension_travel=suspension_travel[3],
            ),
        )

        # --------------------------------------------------
        # Timestamp
        # --------------------------------------------------

        timestamp = getattr(frame, "timestamp", None)

        if timestamp is None:
            import time
            timestamp = time.perf_counter()

        return VehicleMotion(
            timestamp=timestamp,

            pitch_rad=pitch_rad,
            roll_rad=roll_rad,

            lateral_g=lateral_g,
            vertical_g=vertical_g,
            longitudinal_g=longitudinal_g,

            wheels=wheels,
        )