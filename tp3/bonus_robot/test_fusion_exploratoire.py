"""La recherche de raccord retrouve une pose connue sur une scène synthétique."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fusion_exploratoire import estimate_on_prior  # noqa: E402
from localisation import ScanReference  # noqa: E402


class FusionExploratoireTests(unittest.TestCase):
    def test_known_synthetic_pose(self):
        rng = np.random.default_rng(8)
        reference = np.vstack([
            np.column_stack([np.linspace(-3, 4, 75), np.zeros(75)]),
            np.column_stack([np.full(55, -3), np.linspace(0, 5, 55)]),
            rng.uniform([-2, -1], [3, 3], (55, 2)),
        ])
        truth = np.array([.7, -.35, 35.])
        radians = np.deg2rad(truth[2])
        rotation = np.array([[np.cos(radians), -np.sin(radians)],
                             [np.sin(radians), np.cos(radians)]])
        query = (reference - truth[:2]) @ rotation
        pose, quality = estimate_on_prior(query, reference, ScanReference(reference, resolution=.12))
        np.testing.assert_allclose(pose[:2], truth[:2], atol=.1)
        self.assertLess(abs(pose[2] - truth[2]), 2.)
        self.assertLess(quality["score_m2"], .01)


if __name__ == "__main__":
    unittest.main()
