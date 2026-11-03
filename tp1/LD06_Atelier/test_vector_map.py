import unittest
import numpy as np
from vector_map import *

class SegmentTests(unittest.TestCase):
    def test_cut_longer(self):
        np.testing.assert_allclose(cut_longest([[0,0],[4,0]],[[1,-1],[1,1]]),[[1,0],[4,0]])
    def test_equal_preserves_first(self):
        np.testing.assert_allclose(cut_longest([[0,0],[4,0]],[[2,-1],[2,1]]),[[0,0],[2,0]])
        np.testing.assert_allclose(cut_longest([[0,0],[4,0]],[[2-EPS/4,-1],[2-EPS/4,1]])[0],[0,0])
    def test_endpoints_no_cut(self):
        a=np.array([[0,0],[4,0]])
        for x in [0,4,EPS/2,4-EPS/2]:np.testing.assert_allclose(cut_longest(a,[[x,-1],[x,1]]),a)
    def test_cutter_endpoint_allowed(self):
        np.testing.assert_allclose(cut_longest([[0,0],[4,0]],[[1,0],[1,1]]),[[1,0],[4,0]])
    def test_outside_and_collinear(self):
        a=np.array([[0,0],[4,0]])
        for b in [[[1,1],[1,2]],[[5,-1],[5,1]],[[1,0],[3,0]]]:
            self.assertIsNone(intersection(a,b));np.testing.assert_allclose(cut_longest(a,b),a)
    def test_angles_and_merge(self):
        a=[[0,0],[2,0]]
        self.assertAlmostEqual(angle_between(a,[[3,0],[1,0]]),0)
        self.assertAlmostEqual(angle_between(a,[[0,0],[0,1]]),90)
        self.assertTrue(are_close(a,[[2.1,.02],[3,.02]]))
        self.assertFalse(are_close(a,[[0,1],[2,1]]))
        self.assertFalse(are_close(a,[[4,0],[5,0]]))
        self.assertIsNotNone(merge_segments(a,[[2.1,0],[3,0]]))
    def test_extract_corner_and_gap(self):
        p=np.vstack([np.column_stack([np.linspace(1,3,30),np.ones(30)]),np.column_stack([np.full(30,3),np.linspace(1,3,30)])])
        self.assertEqual(len(extract_segments(p)),2)
    def test_update_merge_export(self):
        p=np.column_stack([np.linspace(1,3,40),np.ones(40)])
        m=VectorMap();m.update(p,[0,0,0]);m.update(p,[0,0,0])
        self.assertEqual(len(m.features),1);self.assertEqual(m.features[0]['observations'],2)
    def test_gap_splits_clusters(self):
        p=np.column_stack([np.r_[np.linspace(1,2,15),np.linspace(4,5,15)],np.ones(30)])
        self.assertEqual(len(extract_segments(p)),2)
    def test_ray_clears_crossed_feature(self):
        m=VectorMap();m.features=[dict(segment=np.array([[1.,-1.],[1.,1.]]),observations=1,last_seen=0)]
        m.update(np.array([[2.,0.]]),[0,0,0])
        np.testing.assert_allclose(m.features[0]['segment'],[[1,-1],[1,0]])
    def test_degenerate_rejected(self):
        with self.assertRaises(ValueError):segment([[0,0],[0,0]])

if __name__=='__main__':unittest.main()
