"""Game-independent 3DOF motion-cueing engine.

Outputs are virtual commands for software testing only:
- pitch_deg: requested platform pitch in degrees
- roll_deg: requested platform roll in degrees
- heave_norm: normalized vertical cue in [-1, +1]

These are NOT actuator positions and are not ready to send directly to hardware.
Virtual limits and gains require in-game tuning; physical limits are not known yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import degrees, exp, isfinite

from telemetry import VehicleMotion


@dataclass(frozen=True)
class MotionCommand:
    pitch_deg: float
    roll_deg: float
    heave_norm: float
    timestamp: float
    source: str = "acevo"
    valid: bool = True


@dataclass(frozen=True)
class MotionConfig:
    # Software preview limits only; these are not hardware safety limits.
    max_pitch_deg: float = 10.0
    max_roll_deg: float = 10.0
    max_heave_norm: float = 1.0

    # Vehicle body attitude contribution. Default 0: the simple method uses
    # only the G-force cue, because body roll has the opposite sign to lateral G
    # and the two partly cancelled each other in the first live logs.
    pitch_attitude_gain: float = 0.0
    roll_attitude_gain: float = 0.0

    # Direction switches: flip to -1.0 if the virtual platform leans the wrong
    # way in the in-game check (see README).
    pitch_sign: float = 1.0
    roll_sign: float = 1.0

    # Transient acceleration cue gains.
    longitudinal_g_gain: float = 3.0
    lateral_g_gain: float = 3.0
    vertical_g_gain: float = 0.50

    # Low-pass smoothing for vehicle attitude and cue outputs.
    pitch_filter_tau_s: float = 0.10
    roll_filter_tau_s: float = 0.10
    heave_filter_tau_s: float = 0.12

    # Washout removes sustained acceleration so the platform cue tends to
    # return toward neutral during a long constant-g event.
    longitudinal_washout_tau_s: float = 1.8
    lateral_washout_tau_s: float = 1.8
    vertical_washout_tau_s: float = 0.8

    # Software slew-rate limits for smooth command transitions.
    max_pitch_rate_deg_s: float = 60.0
    max_roll_rate_deg_s: float = 60.0
    max_heave_rate_s: float = 3.0

    # Reject unreasonable dt after pauses/stalls; caller should reinitialize
    # after a genuine disconnect rather than applying a large catch-up step.
    max_dt_s: float = 0.05


class MotionController:
    """Convert normalized telemetry into smoothed pitch/roll/heave cues."""

    def __init__(self, config: MotionConfig | None = None):
        self.config = config or MotionConfig()
        self._pitch = 0.0
        self._roll = 0.0
        self._heave = 0.0
        self._long_g_lp = 0.0
        self._lat_g_lp = 0.0
        self._vert_g_lp = 0.0
        self._initialized = False

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(value, high))

    @staticmethod
    def _finite(value: float) -> float:
        return value if isfinite(value) else 0.0

    @staticmethod
    def _filter(current: float, target: float, dt: float, tau: float) -> float:
        if tau <= 0:
            return target
        alpha = 1.0 - exp(-max(0.0, dt) / tau)
        return current + (target - current) * alpha

    @staticmethod
    def _rate_limit(current: float, target: float, max_rate: float, dt: float) -> float:
        max_step = max(0.0, max_rate) * max(0.0, dt)
        delta = target - current
        return current + max(-max_step, min(delta, max_step))

    def reset(self) -> None:
        """Clear all cue/filter state after disconnect or session reset."""
        self._pitch = self._roll = self._heave = 0.0
        self._long_g_lp = self._lat_g_lp = self._vert_g_lp = 0.0
        self._initialized = False

    def update(self, motion: VehicleMotion, dt: float) -> MotionCommand:
        c = self.config
        dt = self._clamp(self._finite(dt), 0.0, c.max_dt_s)

        # Invalid/inactive session data should not create fresh motion cues.
        if not motion.session_active:
            self.reset()
            return MotionCommand(0.0, 0.0, 0.0, motion.timestamp, motion.source, False)

        pitch_rad = self._finite(motion.pitch_rad)
        roll_rad = self._finite(motion.roll_rad)
        long_g = self._finite(motion.longitudinal_g)
        lat_g = self._finite(motion.lateral_g)
        vert_g = self._finite(motion.vertical_g)

        if not self._initialized:
            # Initialize washout low-pass states to the current measured g.
            # This prevents a large artificial transient on the first sample.
            self._long_g_lp = long_g
            self._lat_g_lp = lat_g
            self._vert_g_lp = vert_g
            self._initialized = True

        # High-pass acceleration cues = current acceleration - slow component.
        # Sustained acceleration gradually washes out instead of holding tilt.
        self._long_g_lp = self._filter(
            self._long_g_lp, long_g, dt, c.longitudinal_washout_tau_s
        )
        self._lat_g_lp = self._filter(
            self._lat_g_lp, lat_g, dt, c.lateral_washout_tau_s
        )
        self._vert_g_lp = self._filter(
            self._vert_g_lp, vert_g, dt, c.vertical_washout_tau_s
        )
        long_transient = long_g - self._long_g_lp
        lat_transient = lat_g - self._lat_g_lp
        vert_transient = vert_g - self._vert_g_lp

        # Attitude and acceleration are separate components so their gains can
        # be tuned independently for each vehicle/game adapter.
        target_pitch = c.pitch_sign * (
            degrees(pitch_rad) * c.pitch_attitude_gain
            + long_transient * c.longitudinal_g_gain
        )
        target_roll = c.roll_sign * (
            degrees(roll_rad) * c.roll_attitude_gain
            + lat_transient * c.lateral_g_gain
        )
        target_heave = vert_transient * c.vertical_g_gain

        target_pitch = self._clamp(target_pitch, -c.max_pitch_deg, c.max_pitch_deg)
        target_roll = self._clamp(target_roll, -c.max_roll_deg, c.max_roll_deg)
        target_heave = self._clamp(
            target_heave, -c.max_heave_norm, c.max_heave_norm
        )

        pitch_filtered = self._filter(self._pitch, target_pitch, dt, c.pitch_filter_tau_s)
        roll_filtered = self._filter(self._roll, target_roll, dt, c.roll_filter_tau_s)
        heave_filtered = self._filter(self._heave, target_heave, dt, c.heave_filter_tau_s)

        self._pitch = self._rate_limit(
            self._pitch, pitch_filtered, c.max_pitch_rate_deg_s, dt
        )
        self._roll = self._rate_limit(
            self._roll, roll_filtered, c.max_roll_rate_deg_s, dt
        )
        self._heave = self._rate_limit(
            self._heave, heave_filtered, c.max_heave_rate_s, dt
        )

        return MotionCommand(
            pitch_deg=self._pitch,
            roll_deg=self._roll,
            heave_norm=self._heave,
            timestamp=motion.timestamp,
            source=motion.source,
            valid=True,
        )
