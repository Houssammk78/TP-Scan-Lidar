import unittest
import numpy as np
from localisation import *
from simulation import scene,raycast

class LocalisationTests(unittest.TestCase):
 def test_wrap(self):
  self.assertEqual(wrap(359),-1);self.assertEqual(wrap(-181),179)
 def test_segment_distance(self):
  ref=VectorReference.__new__(VectorReference);ref.segments=np.array([[[0.,0.],[2.,0.]]])
  np.testing.assert_allclose(ref.residuals(np.array([[1,1],[3,0],[-1,0]])),[1,1,1])
 def test_grid_outside_penalized(self):
  p=raycast(scene(),[0,0,0],count=180);r=GridReference(p,.1)
  self.assertEqual(r.residuals(np.array([[100.,100.]]))[0],1.)
 def test_ray_truth(self):
  wall=np.array([[[2.,-2.],[2.,2.]]]);p=raycast(wall,[0,0,0],noise=0,count=4)
  np.testing.assert_allclose(p,[[2,0]],atol=1e-7)
 def test_icp_known_pose(self):
  ref=raycast(scene(),[0,0,0],seed=5,count=180,noise=0);pose=np.array([.2,-.1,3.])
  # Inverse rigid transform of the same cloud gives an exact numerical test.
  query=apply_pose(ref-pose[:2],0,0,-pose[2]);actual,_=icp(query,ScanReference(ref),[.15,-.05,2.])
  np.testing.assert_allclose(actual,pose,atol=1e-3)
 def test_map_solvers(self):
  ref=raycast(scene(),[0,0,0],seed=1,count=180,noise=0)
  query=raycast(scene(),[.2,.1,2],seed=2,count=180,noise=0)[::2]
  for cls in [GridReference,VectorReference]:
   actual,_=multiresolution(query,cls(ref),[.15,.05,1])
   self.assertLess(np.linalg.norm(actual[:2]-[.2,.1]),.15);self.assertLess(abs(wrap(actual[2]-2)),3)
 def test_invalid_scan(self):
  with self.assertRaises(ValueError):valid_scan([[0,0]])

if __name__=='__main__':unittest.main()
