"""Offline tests for the GUI engine, wording, and profile storage (no tkinter needed)."""
import tempfile
import time
import unittest
from pathlib import Path

import ui_text as T
from engine import MotionRunner, test_pattern
from motion import MotionConfig
from settings_store import config_from_dict, config_to_dict, load_profiles, save_profile
from telemetry import VehicleMotion, WheelMotion


def frame(lat=0.0, long=0.0, active=True):
    w = WheelMotion()
    return VehicleMotion(timestamp=time.perf_counter(), pitch_rad=0.0, roll_rad=0.0,
                         lateral_g=lat, vertical_g=0.0, longitudinal_g=long,
                         wheels=(w, w, w, w), source="fake", session_active=active)


class FakeReader:
    def __init__(self):
        self.frames = []
        self.stopped = False

    async def start(self):
        pass

    async def stop(self):
        self.stopped = True

    def get_latest(self):
        return self.frames.pop(0) if self.frames else None


def wait_for(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


class EngineTests(unittest.TestCase):
    def test_connected_then_stale_then_stop(self):
        reader = FakeReader()
        runner = MotionRunner(reader_factory=lambda g, hz, swap: reader)
        runner.start("lmu", 100)
        reader.frames.extend(frame(long=0.0) for _ in range(3))
        self.assertTrue(wait_for(lambda: runner.snapshot().state == "connected"))
        reader.frames.extend(frame(long=-1.5) for _ in range(30))   # braking burst
        self.assertTrue(wait_for(lambda: runner.snapshot().command is not None
                                 and runner.snapshot().command.pitch_deg < -0.5))
        self.assertEqual(runner.snapshot().game, "lmu")
        self.assertTrue(wait_for(lambda: runner.snapshot().state == "stale", timeout=2.0))
        self.assertEqual(runner.snapshot().command.pitch_deg, 0.0)   # neutral, not held
        runner.stop()
        self.assertEqual(runner.snapshot().state, "idle")
        self.assertTrue(reader.stopped)
        self.assertFalse(runner.is_running())

    def test_config_change_applies_live(self):
        reader = FakeReader()
        runner = MotionRunner(reader_factory=lambda g, hz, swap: reader)
        runner.set_config(MotionConfig(pitch_sign=-1.0))
        runner.start("ac", 100)
        reader.frames.extend(frame(long=0.0) for _ in range(3))
        reader.frames.extend(frame(long=-1.5) for _ in range(30))
        self.assertTrue(wait_for(lambda: runner.snapshot().command is not None
                                 and runner.snapshot().command.pitch_deg > 0.5))
        runner.stop()

    def test_error_is_reported(self):
        def boom(g, hz, swap):
            raise RuntimeError("нет SDK")
        runner = MotionRunner(reader_factory=boom)
        runner.start("acevo", 100)
        self.assertTrue(wait_for(lambda: runner.snapshot().state == "error"))
        self.assertIn("нет SDK", runner.snapshot().message)

    def test_test_mode_produces_motion_and_ends(self):
        runner = MotionRunner()
        runner.start_test(100)
        self.assertTrue(wait_for(lambda: runner.snapshot().state == "test"))
        self.assertTrue(wait_for(lambda: abs(runner.snapshot().command.pitch_deg) > 1.0, 3.0))
        runner.stop()

    def test_pattern_phases(self):
        self.assertEqual(test_pattern(0.0)[1:], (0.0, 0.0))
        p, r, h = test_pattern(4.5)
        self.assertEqual((p, h), (0.0, 0.0))
        self.assertNotEqual(r, 0.0)

    def test_rate_333_runs(self):
        reader = FakeReader()
        runner = MotionRunner(reader_factory=lambda g, hz, swap: reader)
        runner.start("lmu", 333)
        self.assertTrue(wait_for(lambda: runner.snapshot().loop_hz > 250, timeout=3.0))
        runner.stop()


class TextTests(unittest.TestCase):
    def test_directions(self):
        self.assertIn("вперёд", T.pitch_text(-3.0))
        self.assertIn("назад", T.pitch_text(3.0))
        self.assertIn("влево", T.roll_text(-2.0))
        self.assertIn("вправо", T.roll_text(2.0))
        self.assertIn("вверх", T.heave_text(0.5))
        self.assertIn("вниз", T.heave_text(-0.5))
        self.assertIn("в центре", T.pitch_text(0.01))
        self.assertIn("торможение", T.long_g_text(-1.0))
        self.assertIn("вправо", T.lat_g_text(-1.2))   # right turn = negative lateral


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            cfg = MotionConfig(longitudinal_g_gain=5.0, roll_sign=-1.0)
            save_profile("lmu", cfg, path)
            loaded = load_profiles(path)["lmu"]
            self.assertEqual(loaded.longitudinal_g_gain, 5.0)
            self.assertEqual(loaded.roll_sign, -1.0)
            path.write_text("{ broken", encoding="utf-8")
            self.assertEqual(load_profiles(path), {})
        self.assertEqual(config_from_dict({"hax": 1, "max_pitch_deg": "x"}), MotionConfig())
        self.assertIn("pitch_sign", config_to_dict(MotionConfig()))


if __name__ == "__main__":
    unittest.main()
