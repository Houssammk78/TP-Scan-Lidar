import tempfile,unittest
from pathlib import Path
import numpy as np
from grid_map import GridMap,bresenham,build_grid

class GridTests(unittest.TestCase):
    def test_ray_octants(self):
        for end in [(3,0),(-3,0),(0,3),(0,-3),(3,2),(-3,2),(2,-3),(-2,-3),(0,0)]:
            points=list(bresenham((0,0),end));self.assertEqual(points[0],(0,0));self.assertEqual(points[-1],end)
            self.assertEqual(len(points),max(map(abs,end))+1)
            if len(points)>1:self.assertTrue((np.abs(np.diff(points,axis=0))<=1).all())
    def test_unknown_free_impact(self):
        g=GridMap([0,0],[5,5],1);g.update([[3,0]],[.5,.5,0])
        self.assertTrue((g.cells[0,:3]==0).all());self.assertEqual(g.cells[0,3],100);self.assertEqual(g.cells[4,4],-1)
    def test_negative_coordinates(self):
        g=GridMap([-2,-2],[4,4],1);self.assertEqual(g.index([-1.1,-.1]),(0,1))
    def test_rotation_translation(self):
        g=GridMap([-2,-2],[6,6],.5);g.update([[1,0]],[1,0,90]);x,y=g.index([1,1]);self.assertEqual(g.cells[y,x],100)
    def test_conflict_and_order(self):
        a=GridMap([0,0],[5,5],1);b=GridMap([0,0],[5,5],1)
        a.update([[1,0],[3,0]],[.5,.5,0]);b.update([[3,0],[1,0]],[.5,.5,0]);np.testing.assert_array_equal(a.cells,b.cells);self.assertEqual(a.cells[0,1],100)
        a.update([[3,0]],[.5,.5,0]);self.assertEqual(a.cells[0,1],0)
    def test_invalid_outside(self):
        g=GridMap([0,0],[5,5],1);g.update([[float('nan'),0],[0,0],[13,0],[6,0]],[.5,.5,0]);self.assertTrue((g.cells==-1).all())
        with self.assertRaises(ValueError):g.update([[1,0]],[-1,0,0])
    def test_roundtrip_update(self):
        g=GridMap([0,0],[5,5],1);g.update([[1,0]],[.5,.5,0])
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'grid';g.export(prefix);loaded=GridMap.load(str(prefix)+'.npz');np.testing.assert_array_equal(g.cells,loaded.cells)
            loaded.update([[3,0]],[.5,.5,0]);self.assertEqual(loaded.scan_count,2);self.assertEqual(loaded.cells[0,1],0)
    def test_resolution(self):
        with self.assertRaises(ValueError):GridMap([0,0],[1,1],0)
        g=build_grid([np.array([[1.,0.]])],[[0,0,0]],.05);self.assertEqual(g.scan_count,1)

if __name__=='__main__':unittest.main()
