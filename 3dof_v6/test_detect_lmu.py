"""Offline tests: LMU adapter on a fake LMU_Data buffer, and auto-detection logic."""
import asyncio
import ctypes
import threading
import time as _t
import unittest

import detect
import telemetry_lmu as L
from telemetry_ac import _GraphicsHead, _PhysicsHead


def lmu_buffer(*, version=1, has_vehicle=True, idx=0, active=1, elapsed=10.0,
               accel=(0.0, 0.0, 0.0), loads=(1000, 2000, 3000, 4000)):
    buf = bytearray(L.ROOT_SIZE)
    ctypes.c_int32.from_buffer(buf, L.GAME_VERSION_OFFSET).value = version
    head = L._TelemetryHead.from_buffer(buf, L.TELEMETRY_OFFSET)
    head.activeVehicles, head.playerVehicleIdx, head.playerHasVehicle = active, idx, has_vehicle
    v = L._Vehicle.from_buffer(buf, L.TELEMETRY_OFFSET + 4 + idx * L.VEHICLE_SIZE)
    v.mElapsedTime = elapsed
    v.mLocalAccel.x, v.mLocalAccel.y, v.mLocalAccel.z = accel
    for i in range(4):
        v.mWheels[i].mTireLoad = loads[i]
        v.mWheels[i].mSuspensionDeflection = 0.01 * (i + 1)
    return buf


class LmuTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(ctypes.sizeof(L._Vehicle), 1888)
        self.assertEqual(L.TELEMETRY_OFFSET + 4 + 104 * 1888, L.ROOT_SIZE)

    def test_maps_and_signs(self):
        # rF2 axes: x left, y up, z rearward. Right turn -> x negative.
        # Braking -> accel vector points rearward -> z positive.
        buf = lmu_buffer(accel=(-9.80665, 0.0, 9.80665))
        m = L.LmuSharedMemoryReader(opener=lambda: buf).get_latest()
        self.assertAlmostEqual(m.lateral_g, -1.0, places=5)       # right turn
        self.assertAlmostEqual(m.longitudinal_g, -1.0, places=5)  # braking
        self.assertAlmostEqual(m.wheels[3].load, 4000.0)
        self.assertAlmostEqual(m.wheels[1].suspension_travel, 0.02)
        self.assertEqual(m.source, "lmu")

    def test_same_frame_once_new_frame_again(self):
        buf = lmu_buffer(elapsed=5.0)
        r = L.LmuSharedMemoryReader(opener=lambda: buf)
        self.assertIsNotNone(r.get_latest())
        self.assertIsNone(r.get_latest())
        buf[:] = lmu_buffer(elapsed=5.01)
        self.assertIsNotNone(r.get_latest())

    def test_player_index_used(self):
        buf = lmu_buffer(idx=3, active=5, accel=(0.0, 0.0, 0.0), elapsed=2.0)
        self.assertIsNotNone(L.LmuSharedMemoryReader(opener=lambda: buf).get_latest())

    def test_no_player_or_bad_index(self):
        self.assertIsNone(L.LmuSharedMemoryReader(
            opener=lambda: lmu_buffer(has_vehicle=False)).get_latest())
        self.assertIsNone(L.LmuSharedMemoryReader(
            opener=lambda: lmu_buffer(idx=7, active=2)).get_latest())

    def test_game_ready(self):
        self.assertTrue(L.LmuSharedMemoryReader(opener=lambda: lmu_buffer()).game_ready())
        self.assertFalse(L.LmuSharedMemoryReader(opener=lambda: lmu_buffer(version=0)).game_ready())
        self.assertFalse(L.LmuSharedMemoryReader(opener=lambda: None).game_ready())


def _phys(packet, loads):
    p = _PhysicsHead()
    p.packetId = packet
    for i in range(4):
        p.wheelLoad[i] = loads[i]
    return bytearray(p)


class DetectTests(unittest.TestCase):
    def _opener(self, loads, status=2):
        gfx = _GraphicsHead()
        gfx.status = status
        live = bytearray(_phys(1, loads))
        return (lambda kind: live if kind == "physics" else bytearray(gfx)), live

    def test_ac_vs_acc_classification(self):
        for loads, expected in (((2000, 2100, 2900, 2800), "ac"), ((0, 0, 0, 0), "acc")):
            opener, live = self._opener(loads)
            stop = threading.Event()
            def tick():
                n = 2
                while not stop.is_set():
                    live[:] = _phys(n, loads); n += 1; _t.sleep(0.002)
            t = threading.Thread(target=tick); t.start()
            try:
                self.assertEqual(detect.probe_ac_family(opener=opener, window_s=0.5), expected)
            finally:
                stop.set(); t.join()

    def test_frozen_physics_is_not_detected(self):
        opener, _ = self._opener((2000, 2000, 2000, 2000))
        self.assertIsNone(detect.probe_ac_family(opener=opener, window_s=0.1))

    def test_game_absent(self):
        self.assertIsNone(detect.probe_ac_family(opener=lambda k: None, window_s=0.05))

    def test_find_and_select(self):
        async def run(found_lists, chosen=None):
            it = iter(found_lists)
            async def find(include_evo=True):
                return next(it)
            return await detect.auto_select(find=find, ask=lambda f: chosen or f[0],
                                            announce=lambda *_: None, poll_s=0.0, max_attempts=5)
        self.assertEqual(asyncio.run(run([[], [], ["acc"]])), "acc")
        self.assertEqual(asyncio.run(run([["ac", "lmu"]], chosen="lmu")), "lmu")

    def test_find_running_games_combines_probes(self):
        async def evo(): return True
        found = asyncio.run(detect.find_running_games(
            True, ac_probe=lambda: "acc", lmu_probe=lambda: False, evo_probe=evo))
        self.assertEqual(found, ["acc", "acevo"])


if __name__ == "__main__":
    unittest.main()
