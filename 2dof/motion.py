from dataclasses import dataclass
from math import degrees

from telemetry import VehicleMotion


# ------------------------------------------------------------
# LIMITS
# ------------------------------------------------------------

MAX_PITCH_DEG = 10.0
MAX_ROLL_DEG = 10.0


# ------------------------------------------------------------
# SENSITIVITY
# ------------------------------------------------------------

PITCH_SCALE = 0.50
ROLL_SCALE = 0.50

G_PITCH_SCALE = 4.0
G_ROLL_SCALE = 4.0


# ------------------------------------------------------------
# FILTER
# ------------------------------------------------------------

FILTER_ALPHA = 0.15


# ------------------------------------------------------------
# DIRECTION
# ------------------------------------------------------------

# Если направление окажется обратным,
# просто поменяем 1.0 на -1.0.

PITCH_DIRECTION = 1.0
ROLL_DIRECTION = 1.0


@dataclass
class MotionCommand:
    pitch_deg: float
    roll_deg: float


class MotionController:

    def __init__(self):
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0

    @staticmethod
    def clamp(value, minimum, maximum):
        return max(minimum, min(value, maximum))

    def update(self, motion: VehicleMotion) -> MotionCommand:

        # ----------------------------------------------------
        # CAR ORIENTATION
        # ----------------------------------------------------

        raw_pitch_deg = degrees(motion.pitch_rad)
        raw_roll_deg = degrees(motion.roll_rad)

        # ----------------------------------------------------
        # G-FORCES
        # ----------------------------------------------------

        longitudinal_g = motion.longitudinal_g
        lateral_g = motion.lateral_g

        # ----------------------------------------------------
        # MOTION CUE
        # ----------------------------------------------------

        target_pitch = (
            raw_pitch_deg * PITCH_SCALE
            + longitudinal_g * G_PITCH_SCALE
        )

        target_roll = (
            raw_roll_deg * ROLL_SCALE
            + lateral_g * G_ROLL_SCALE
        )

        # ----------------------------------------------------
        # DIRECTION
        # ----------------------------------------------------

        target_pitch *= PITCH_DIRECTION
        target_roll *= ROLL_DIRECTION

        # ----------------------------------------------------
        # HARD LIMIT
        # ----------------------------------------------------

        target_pitch = self.clamp(
            target_pitch,
            -MAX_PITCH_DEG,
            MAX_PITCH_DEG,
        )

        target_roll = self.clamp(
            target_roll,
            -MAX_ROLL_DEG,
            MAX_ROLL_DEG,
        )

        # ----------------------------------------------------
        # LOW PASS FILTER
        # ----------------------------------------------------

        self.filtered_pitch += (
            target_pitch - self.filtered_pitch
        ) * FILTER_ALPHA

        self.filtered_roll += (
            target_roll - self.filtered_roll
        ) * FILTER_ALPHA

        return MotionCommand(
            pitch_deg=self.filtered_pitch,
            roll_deg=self.filtered_roll,
        )