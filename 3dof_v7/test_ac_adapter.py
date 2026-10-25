"""Offline tests for the AC/ACC adapter using fake shared-memory buffers."""
import unittest

from telemetry_ac import (AcSharedMemoryReader, AxisMap, _GraphicsHead,
                          _PhysicsHead, STATUS_LIVE)


def phys(packet=1, acc=(0.0, 0.0, 0.0), pitch=0.0, roll=0.0,
         load=(1, 2, 3, 4), travel=(0.01, 0.02, 0.03, 0.04)):
    p = _PhysicsHead()
    p.packetId = packet
    for i in range(3):
        p.accG[i] = acc[i]
    for i in range(4):
        p.wheelLoad[i] = load[i]
        p.suspensionTravel[i] = travel[i]
    p.pitch, p.roll = pitch, roll
    return bytearray(p)


def gfx(status=STATUS_LIVE):
    g = _GraphicsHead()
    g.status = status
    return bytearray(g)


def reader(pbuf, gbuf, **kw):
    pages = {"physics": pbuf, "graphics": gbuf}
    return AcSharedMemoryReader(opener=lambda k: pages[k], **kw)


class AcAdapterTests(unittest.TestCase):
    def test_maps_fields(self):
        r = reader(phys(acc=(1.2, 0.1, 0.3), pitch=0.05, roll=-0.02), gfx())
        m = r.get_latest()
        self.assertEqual((m.lateral_g, m.longitudinal_g), (
            m.lateral_g, m.longitudinal_g))
        self.assertAlmostEqual(m.lateral_g, 1.2, places=5)
        self.assertAlmostEqual(m.vertical_g, 0.1, places=5)
        self.assertAlmostEqual(m.longitudinal_g, 0.3, places=5)
        self.assertAlmostEqual(m.pitch_rad, 0.05, places=5)
        self.assertAlmostEqual(m.roll_rad, -0.02, places=5)
        self.assertAlmostEqual(m.wheels[3].load, 4.0)
        self.assertAlmostEqual(m.wheels[1].suspension_travel, 0.02, places=6)
        self.assertEqual(m.source, "ac")
        self.assertTrue(m.session_active)

    def test_same_packet_returned_once(self):
        r = reader(phys(packet=7), gfx())
        self.assertIsNotNone(r.get_latest())
        self.assertIsNone(r.get_latest())

    def test_new_packet_returned(self):
        pbuf = phys(packet=1)
        r = reader(pbuf, gfx())
        r.get_latest()
        pbuf[:] = phys(packet=2)
        self.assertIsNotNone(r.get_latest())

    def test_pause_marks_inactive(self):
        r = reader(phys(), gfx(status=3))
        self.assertFalse(r.get_latest().session_active)

    def test_axis_map_and_signs(self):
        axes = AxisMap(lateral_index=0, longitudinal_index=1, vertical_index=2,
                       longitudinal_sign=-1.0)
        r = reader(phys(acc=(0.5, 0.8, 0.1)), gfx(), axes=axes)
        m = r.get_latest()
        self.assertAlmostEqual(m.longitudinal_g, -0.8, places=5)
        self.assertAlmostEqual(m.vertical_g, 0.1, places=5)

    def test_game_not_running(self):
        r = AcSharedMemoryReader(opener=lambda k: None)
        self.assertIsNone(r.get_latest())

    def test_game_appears_later(self):
        pages = {}
        r = AcSharedMemoryReader(opener=lambda k: pages.get(k))
        r.RETRY_OPEN_S = 0.0
        self.assertIsNone(r.get_latest())
        pages["physics"], pages["graphics"] = phys(), gfx()
        self.assertIsNotNone(r.get_latest())


if __name__ == "__main__":
    unittest.main()
