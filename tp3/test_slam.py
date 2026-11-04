"""Tests du recalage incrémental sans pose TP1/TP2 préenregistrée."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slam import REPO, estimate_pose, expand_grid, make_grid, run  # noqa: E402


class SlamTests(unittest.TestCase):
    def test_new_scan_localized_from_scan_geometry(self):
        reference = np.random.default_rng(4).uniform([-2, -1.5], [3, 2.5], (80, 2))
        truth = np.array([.7, -.35, 25.])
        theta = np.deg2rad(truth[2])
        rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        query = (reference - truth[:2]) @ rotation
        pose, _, info, _ = estimate_pose(query, reference, np.zeros(3))
        np.testing.assert_allclose(pose, truth, atol=.03)
        self.assertLess(info["score"], .001)

    def test_new_scan_expands_map_before_ray_update(self):
        first = np.array([[1., 0.], [0., 1.], [-1., 0.], [0., -1.]])
        grid = make_grid(first, resolution=.1)
        old_width = grid.cells.shape[1]
        new = np.array([[2., 0.]])
        pose = np.array([8., 0., 0.])
        expand_grid(grid, new, pose)
        self.assertGreater(grid.cells.shape[1], old_width)
        grid.update(new, pose)
        x, y = grid.index([10., 0.])
        self.assertEqual(grid.cells[y, x], 100)
        self.assertEqual(grid.scan_count, 1)

    def test_replay_two_real_scans_without_saved_poses(self):
        folder = REPO / "tp2" / "acquisitions" / "position_A_20261103_120212"
        sources = [("A_01", folder / "A_01.csv"), ("A_02", folder / "A_02.csv")]
        with tempfile.TemporaryDirectory() as tmp:
            rows = run(sources, tmp)
            self.assertEqual([row["status"] for row in rows], ["ajoute", "ajoute"])
            self.assertLess(np.linalg.norm(rows[1]["pose_estimee"][:2]), .1)
            self.assertTrue((Path(tmp) / "grid_map.npz").is_file())
            self.assertTrue((Path(tmp) / "carte_finale.png").is_file())


if __name__ == "__main__":
    unittest.main()
