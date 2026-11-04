"""Contrôles du format LD06, des doublons et de l'arrêt du pilotage."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_slam import decode_packet, front_clearance, live, load_acquisition  # noqa: E402


class FakeRobot:
    def __init__(self, distance):
        self.distance = distance
        self.commands = []

    def stop(self):
        self.commands.append("stop")

    def fresh_scan(self, name):
        from mobile_slam import Scan
        angles = np.linspace(-50, 50, 81)
        cloud = np.column_stack([self.distance * np.cos(np.deg2rad(angles)),
                                 self.distance * np.sin(np.deg2rad(angles))])
        return Scan(name, "test", cloud, len(cloud), "fake")

    def get(self, path):
        self.commands.append(path)
        return b"OK"


class MobileSlamTests(unittest.TestCase):
    def test_binary_scan_coordinates_and_manual_pose(self):
        packet = struct.pack("<hhHH", 14, -22, 9000, 2)
        packet += struct.pack("<HHB", 0, 2000, 200)
        packet += struct.pack("<HHB", 9000, 1000, 150)
        scan = decode_packet(packet)
        np.testing.assert_allclose(scan.points, [[2, 0], [0, -1]], atol=1e-12)
        self.assertEqual(scan.embedded_pose, (14, -22, 90))

    def test_obstacle_prevents_forward_command(self):
        robot = FakeRobot(.5)
        with tempfile.TemporaryDirectory() as folder:
            engine = live(robot, folder, steps=2, min_clearance=.9)
            self.assertEqual(len(engine.rows), 1)
            self.assertTrue((Path(folder) / "scans_bruts" / "L000.csv").is_file())
            self.assertTrue((Path(folder) / "slam_mobile.png").is_file())
        self.assertNotIn("/forward", robot.commands)
        self.assertEqual(robot.commands[-1], "stop")

    def test_one_clear_pulse_is_followed_by_stop_and_new_map(self):
        robot = FakeRobot(2.)
        with tempfile.TemporaryDirectory() as folder:
            engine = live(robot, folder, steps=1, min_clearance=.9)
            self.assertEqual(len(engine.rows), 2)
            self.assertEqual([row["status"] for row in engine.rows], ["ajoute", "ajoute"])
            self.assertTrue((Path(folder) / "scans_bruts" / "L001.csv").is_file())
        self.assertEqual(robot.commands.count("/forward"), 1)
        self.assertEqual(robot.commands[-1], "stop")

    def test_latest_cumulative_export_and_singles_are_deduplicated(self):
        folder = Path(__file__).resolve().parent / "donnees"
        files = sorted(folder.glob("scan_20261104_*.csv"))
        scans = load_acquisition(folder / "tous_scans_ld06_20261104_164353.csv", files)
        self.assertEqual(len(scans), 117)
        self.assertEqual(scans[0].name, "R001")
        self.assertEqual(scans[-1].name, "scan_20261104_165007")


if __name__ == "__main__":
    unittest.main()
