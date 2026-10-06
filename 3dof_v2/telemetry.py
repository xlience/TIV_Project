from dataclasses import dataclass

from acevo import TelemetryCapture


# ============================================================
# WHEEL DATA
# ============================================================

@dataclass
class WheelMotion:
    """
    Data for one wheel.

    Order:
        FL = Front Left
        FR = Front Right
        RL = Rear Left
        RR = Rear Right
    """

    load: float
    suspension_travel: float


# ============================================================
# VEHICLE MOTION
# ============================================================

@dataclass
class VehicleMotion:
    """
    Motion-related data received from Assetto Corsa EVO.
    """

    # Vehicle orientation
    pitch_rad: float
    roll_rad: float

    # Vehicle acceleration
    lateral_g: float
    vertical_g: float
    longitudinal_g: float

    # Four wheels
    wheels: tuple[WheelMotion, WheelMotion, WheelMotion, WheelMotion]


# ============================================================
# TELEMETRY READER
# ============================================================

class TelemetryReader:

    def __init__(self, hz=60):
        self.capture = TelemetryCapture(hz=hz)

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    async def start(self):
        await self.capture.start_capture()

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    async def stop(self):
        await self.capture.stop_capture()

    # --------------------------------------------------------
    # GET MOTION DATA
    # --------------------------------------------------------

    def get_motion(self):

        frames = self.capture.get_frames()

        if not frames:
            return None

        physics = frames[-1].physics

        # ====================================================
        # ORIENTATION
        # ====================================================

        pitch_rad = physics.get("pitch") or 0.0
        roll_rad = physics.get("roll") or 0.0

        # ====================================================
        # G-FORCES
        # ====================================================

        acc_g = physics.get("acc_g") or {}

        lateral_g = acc_g.get("x") or 0.0
        vertical_g = acc_g.get("y") or 0.0
        longitudinal_g = acc_g.get("z") or 0.0

        # ====================================================
        # WHEEL DATA
        # ====================================================

        wheel_load = physics.get("wheel_load") or [
            0.0, 0.0, 0.0, 0.0
        ]

        suspension_travel = physics.get(
            "suspension_travel"
        ) or [
            0.0, 0.0, 0.0, 0.0
        ]

        # Make sure arrays always contain 4 values
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

        # ====================================================
        # RESULT
        # ====================================================

        return VehicleMotion(
            pitch_rad=pitch_rad,
            roll_rad=roll_rad,

            lateral_g=lateral_g,
            vertical_g=vertical_g,
            longitudinal_g=longitudinal_g,

            wheels=wheels,
        )