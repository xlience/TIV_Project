from dataclasses import dataclass
from math import degrees, radians, sin, cos

from telemetry import VehicleMotion


# ============================================================
# DRIVER / STEERING POSITION
# ============================================================

# 0 = center
# 1 = left-hand drive
# 2 = right-hand drive

STEERING_SIDE = 1


# ============================================================
# DRIVER POSITION
# ============================================================

# Future physical dimensions.
#
# X = left/right
# Y = up/down
# Z = front/back
#
# For now all values are 0 because our small prototype
# represents the driver at the center of the platform.

DRIVER_OFFSET_X = 0.0
DRIVER_OFFSET_Y = 0.0
DRIVER_OFFSET_Z = 0.0


# Distance from vehicle center to driver position.
#
# This will become useful when the real platform is built.

DRIVER_LHD_X = -0.5
DRIVER_RHD_X = +0.5


# ============================================================
# PLATFORM LIMITS
# ============================================================

MAX_PITCH_DEG = 10.0
MAX_ROLL_DEG = 10.0

MAX_HEAVE = 1.0


# ============================================================
# PITCH / ROLL SENSITIVITY
# ============================================================

PITCH_SCALE = 0.50
ROLL_SCALE = 0.50

G_PITCH_SCALE = 4.0
G_ROLL_SCALE = 4.0


# ============================================================
# HEAVE
# ============================================================

# Vertical G → platform movement

HEAVE_G_SCALE = 0.50

# Dead zone prevents tiny movements from constantly
# moving the platform.

HEAVE_DEADZONE = 0.05


# ============================================================
# FILTERS
# ============================================================

PITCH_FILTER_ALPHA = 0.15
ROLL_FILTER_ALPHA = 0.15
HEAVE_FILTER_ALPHA = 0.10


# ============================================================
# DIRECTION
# ============================================================

PITCH_DIRECTION = 1.0
ROLL_DIRECTION = 1.0
HEAVE_DIRECTION = 1.0


# ============================================================
# COMMAND
# ============================================================

@dataclass
class MotionCommand:
    pitch_deg: float
    roll_deg: float
    heave: float


# ============================================================
# MOTION CONTROLLER
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
    # DEAD ZONE
    # --------------------------------------------------------

    @staticmethod
    def deadzone(value, zone):

        if abs(value) < zone:
            return 0.0

        return value

    # --------------------------------------------------------
    # DRIVER POSITION
    # --------------------------------------------------------

    def get_driver_offset_x(self):

        if STEERING_SIDE == 0:
            return 0.0

        if STEERING_SIDE == 1:
            return DRIVER_LHD_X

        if STEERING_SIDE == 2:
            return DRIVER_RHD_X

        raise ValueError(
            "STEERING_SIDE must be 0, 1 or 2"
        )

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    def update(self, motion: VehicleMotion):

        # ====================================================
        # CAR ORIENTATION
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
        # DRIVER REFERENCE
        # ====================================================

        driver_x = (
            self.get_driver_offset_x()
            + DRIVER_OFFSET_X
        )

        driver_y = DRIVER_OFFSET_Y
        driver_z = DRIVER_OFFSET_Z

        # Currently these coordinates are mostly preparation
        # for the physical geometry model.
        #
        # They allow us to distinguish:
        #
        # center
        # LHD
        # RHD
        #
        # without rewriting the motion system later.

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
        # DRIVER-SIDE REFERENCE
        # ====================================================

        # For the future physical model we keep the driver's
        # X position available here.
        #
        # At this stage the angular command itself does not
        # change merely because the driver sits left/right.
        #
        # The offset will be used when we calculate the
        # actual 3D position of the driver's seat relative
        # to the platform rotation center.

        _ = driver_x
        _ = driver_y
        _ = driver_z

        # ====================================================
        # HEAVE
        # ====================================================

        heave_input = self.deadzone(
            vertical_g,
            HEAVE_DEADZONE
        )

        target_heave = (
            heave_input * HEAVE_G_SCALE
        )

        # ====================================================
        # DIRECTIONS
        # ====================================================

        target_pitch *= PITCH_DIRECTION
        target_roll *= ROLL_DIRECTION
        target_heave *= HEAVE_DIRECTION

        # ====================================================
        # LIMITS
        # ====================================================

        target_pitch = self.clamp(
            target_pitch,
            -MAX_PITCH_DEG,
            MAX_PITCH_DEG
        )

        target_roll = self.clamp(
            target_roll,
            -MAX_ROLL_DEG,
            MAX_ROLL_DEG
        )

        target_heave = self.clamp(
            target_heave,
            -MAX_HEAVE,
            MAX_HEAVE
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

        # ====================================================
        # RESULT
        # ====================================================

        return MotionCommand(
            pitch_deg=self.filtered_pitch,
            roll_deg=self.filtered_roll,
            heave=self.filtered_heave
        )