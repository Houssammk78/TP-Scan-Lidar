import unittest
import tempfile
from pathlib import Path
import numpy as np
from localisation import *
from simulation import scene,raycast
from evaluer import evaluate,read_measured_poses

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

 def test_batched_cost_matches_scalar_for_maps(self):
  ref=raycast(scene(),[0,0,0],noise=0,count=180)
  query=raycast(scene(),[.2,.1,2],noise=0,count=180)[::3]
  poses=np.array([[0,0,0],[.2,.1,2],[-.3,.25,-5]])
  for model in [GridReference(ref),VectorReference(ref)]:
   np.testing.assert_allclose(objective_batch(model,query,poses),
                              [objective(model,query,pose) for pose in poses],atol=1e-12)

 def test_large_angular_error_is_recovered(self):
  ref=raycast(scene(),[0,0,0],seed=11,count=180)
  truth=np.array([.437,.127,4.3]);query=raycast(scene(),truth,seed=20,count=180)[::3]
  for name,(cls,solver) in METHODS.items():
   pose,_=solver(query,cls(ref),truth+[0,0,90])
   self.assertLess(np.linalg.norm(pose[:2]-truth[:2]),.2,name)
   self.assertLess(abs(wrap(pose[2]-truth[2])),5,name)

 def test_measured_reference_requires_pose_and_uncertainty(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'mesures.csv'
   path.write_text('scan;x_m;y_m;angle_deg;uncertainty_position_m;uncertainty_angle_deg\n'
                   'A_02;;;;;\nB_01;-0,9;0;2;0,05;1\n',encoding='utf-8')
   measurements=read_measured_poses(path)
   self.assertEqual(measurements['B_01']['pose'],[-.9,0.,2.])
   self.assertNotIn('A_02',measurements)
   path.write_text('scan;x_m;y_m;angle_deg;uncertainty_position_m;uncertainty_angle_deg\n'
                   'B_01;-0,9;0;2;;\n',encoding='utf-8')
   with self.assertRaises(ValueError):read_measured_poses(path)

 def test_real_evaluation_uses_only_supplied_ground_truth(self):
  reference=raycast(scene(),[0,0,0],count=180,noise=0)
  pose=[.2,.1,2.]
  query=raycast(scene(),pose,count=180,noise=0)
  rows,_,_=evaluate('reel',reference,{'B_01':query,'B_02':query},[(0,0,0)],{'B_01':pose})
  for row in rows:
   self.assertIsNotNone(row['position_error_m'] if row['scan']=='B_01' else row['residual_rms_capped_m'])
   if row['scan']=='B_02':
    self.assertIsNone(row['position_error_m'])
    self.assertIsNone(row['success'])

if __name__=='__main__':unittest.main()
