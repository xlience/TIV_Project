"""Offline unit tests for the game-independent Motion Engine.

Run from this folder: python -m unittest -v
"""
import unittest
from dataclasses import replace

from motion import MotionCommand, MotionConfig, MotionController
from telemetry import VehicleMotion, WheelMotion


def sample(**changes):
    base = VehicleMotion(
        timestamp=1.0,
        pitch_rad=0.0,
        roll_rad=0.0,
        lateral_g=0.0,
        vertical_g=0.0,
        longitudinal_g=0.0,
        wheels=(WheelMotion(), WheelMotion(), WheelMotion(), WheelMotion()),
    )
    return replace(base, **changes)


class MotionControllerTests(unittest.TestCase):
    def test_zero_input_stays_neutral(self):
        controller = MotionController()
        for i in range(20):
            command = controller.update(sample(timestamp=i / 100), 0.01)
        self.assertAlmostEqual(command.pitch_deg, 0.0)
        self.assertAlmostEqual(command.roll_deg, 0.0)
        self.assertAlmostEqual(command.heave_norm, 0.0)

    def test_output_respects_virtual_limits(self):
        config = MotionConfig(max_pitch_deg=2.0, max_roll_deg=3.0, max_heave_norm=0.2)
        controller = MotionController(config)
        for i in range(100):
            command = controller.update(
                sample(
                    timestamp=i / 100,
                    pitch_rad=1.0,
                    roll_rad=-1.0,
                    longitudinal_g=10.0,
                    lateral_g=-10.0,
                    vertical_g=10.0,
                ),
                0.01,
            )
        self.assertLessEqual(abs(command.pitch_deg), 2.0)
        self.assertLessEqual(abs(command.roll_deg), 3.0)
        self.assertLessEqual(abs(command.heave_norm), 0.2)

    def test_sustained_acceleration_washes_out(self):
        controller = MotionController(MotionConfig(
            pitch_attitude_gain=0.0,
            roll_attitude_gain=0.0,
            longitudinal_g_gain=3.0,
            longitudinal_washout_tau_s=0.25,
            pitch_filter_tau_s=0.03,
            max_pitch_rate_deg_s=1000.0,
        ))
        # First sample establishes the baseline; constant g should wash out.
        for i in range(300):
            command = controller.update(
                sample(timestamp=i / 100, longitudinal_g=0.5), 0.01
            )
        self.assertLess(abs(command.pitch_deg), 0.1)

    def test_rate_limit_bounds_per_step(self):
        config = MotionConfig(
            pitch_attitude_gain=1.0,
            pitch_filter_tau_s=0.001,
            max_pitch_rate_deg_s=10.0,
        )
        controller = MotionController(config)
        command = controller.update(sample(pitch_rad=1.0), 0.01)
        self.assertLessEqual(abs(command.pitch_deg), 0.100001)

    def test_inactive_session_returns_neutral_and_invalid(self):
        controller = MotionController()
        controller.update(sample(pitch_rad=0.2), 0.01)
        command = controller.update(sample(session_active=False), 0.01)
        self.assertFalse(command.valid)
        self.assertEqual(command.pitch_deg, 0.0)
        self.assertEqual(command.roll_deg, 0.0)
        self.assertEqual(command.heave_norm, 0.0)

    def test_nan_input_does_not_propagate(self):
        controller = MotionController()
        command = controller.update(
            sample(longitudinal_g=float("nan"), lateral_g=float("inf")), 0.01
        )
        self.assertTrue(all(map(
            lambda value: value == value and abs(value) != float("inf"),
            (command.pitch_deg, command.roll_deg, command.heave_norm),
        )))

    def test_default_ignores_body_attitude(self):
        controller = MotionController()
        for i in range(50):
            command = controller.update(sample(timestamp=i / 100, roll_rad=0.1, pitch_rad=0.1), 0.01)
        self.assertAlmostEqual(command.roll_deg, 0.0)
        self.assertAlmostEqual(command.pitch_deg, 0.0)

    def test_sign_switch_flips_direction(self):
        def run(sign):
            c = MotionController(MotionConfig(roll_sign=sign))
            c.update(sample(), 0.01)
            for i in range(20):
                cmd = c.update(sample(lateral_g=1.0), 0.01)
            return cmd.roll_deg
        self.assertGreater(run(1.0), 0.0)
        self.assertLess(run(-1.0), 0.0)


if __name__ == "__main__":
    unittest.main()
