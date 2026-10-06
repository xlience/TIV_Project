from dataclasses import dataclass
from math import degrees

from telemetry import VehicleMotion


# ============================================================
# LIMITS
# ============================================================

MAX_PITCH_DEG = 10.0
MAX_ROLL_DEG = 10.0
MAX_HEAVE = 1.0


# ============================================================
# SENSITIVITY
# ============================================================

PITCH_SCALE = 0.50
ROLL_SCALE = 0.50

G_PITCH_SCALE = 4.0
G_ROLL_SCALE = 4.0

HEAVE_G_SCALE = 0.50


# ============================================================
# FILTER
# ============================================================

PITCH_FILTER_ALPHA = 0.15
ROLL_FILTER_ALPHA = 0.15
HEAVE_FILTER_ALPHA = 0.10


# ============================================================
# COMMAND
# ============================================================

@dataclass
class MotionCommand:
    pitch_deg: float
    roll_deg: float
    heave: float


# ============================================================
# CONTROLLER
# ============================================================

class MotionController:

    def __init__(self):

        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.filtered_heave = 0.0

    # --------------------------------------------------------
    # CLAMP
    # --------------------------------------------------------

    @staticmethod
    def clamp(value, minimum, maximum):
        return max(minimum, min(value, maximum))

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    def update(self, motion: VehicleMotion):

        # ====================================================
        # VEHICLE ORIENTATION
        # ====================================================

        raw_pitch_deg = degrees(
            motion.pitch_rad
        )

        raw_roll_deg = degrees(
            motion.roll_rad
        )

        # ====================================================
        # G-FORCES
        # ====================================================

        longitudinal_g = motion.longitudinal_g
        lateral_g = motion.lateral_g
        vertical_g = motion.vertical_g

        # ====================================================
        # PITCH
        # ====================================================

        target_pitch = (
            raw_pitch_deg * PITCH_SCALE
            + longitudinal_g * G_PITCH_SCALE
        )

        # ====================================================
        # ROLL
        # ====================================================

        target_roll = (
            raw_roll_deg * ROLL_SCALE
            + lateral_g * G_ROLL_SCALE
        )

        # ====================================================
        # HEAVE
        # ====================================================

        target_heave = (
            vertical_g * HEAVE_G_SCALE
        )

        # ====================================================
        # LIMITS
        # ====================================================

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

        target_heave = self.clamp(
            target_heave,
            -MAX_HEAVE,
            MAX_HEAVE,
        )

        # ====================================================
        # FILTER
        # ====================================================

        self.filtered_pitch += (
            target_pitch - self.filtered_pitch
        ) * PITCH_FILTER_ALPHA

        self.filtered_roll += (
            target_roll - self.filtered_roll
        ) * ROLL_FILTER_ALPHA

        self.filtered_heave += (
            target_heave - self.filtered_heave
        ) * HEAVE_FILTER_ALPHA

        return MotionCommand(
            pitch_deg=self.filtered_pitch,
            roll_deg=self.filtered_roll,
            heave=self.filtered_heave,
        )