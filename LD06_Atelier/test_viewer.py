"""Verification des callbacks du viewer sans ouvrir de fenetre."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import viewer

class ViewerTests(unittest.TestCase):
    def check_mode(self,mode):
        sliders=[];radios=[];buttons=[]
        real_slider,real_radio,real_button=viewer.Slider,viewer.RadioButtons,viewer.Button
        def slider(*a,**k):
            obj=real_slider(*a,**k);sliders.append(obj);return obj
        def radio(*a,**k):
            obj=real_radio(*a,**k);radios.append(obj);return obj
        def button(*a,**k):
            obj=real_button(*a,**k);buttons.append(obj);return obj
        with tempfile.TemporaryDirectory() as directory:
            root=Path(__file__).resolve().parent.parent
            scans=[root/'TP1_4_scans/data/scan1.csv',root/'TP1_4_scans/data/scan2.csv']
            poses=Path(directory)/'poses.json';poses.write_text((root/'TP1_4_scans/poses.json').read_text())
            output=Path(directory)/'result.csv' if mode=='--vector-map' else Path(directory)/'result'
            export='--export-vectors' if mode=='--vector-map' else '--export-grid'
            def interact():
                radios[0].set_active(1)
                initial=[s.val for s in sliders]
                sliders[0].set_val(initial[0]+.2)
                sliders[2].set_val(initial[2]+1)
                for b in buttons:
                    if b.label.get_text()=='Enregistrer poses':b._observers.process('clicked',None)
                saved=json.loads(poses.read_text());self.assertAlmostEqual(saved[scans[1].name][0],initial[0]+.2)
                for b in buttons:
                    if b.label.get_text().startswith('Exporter'):b._observers.process('clicked',None)
                self.assertTrue(Path(str(output) if mode=='--vector-map' else str(output)+'.npz').exists())
                radios[0].set_active(0)
                self.assertAlmostEqual(sliders[0].val,saved[scans[0].name][0])
                plt.close('all')
            args=['viewer.py',*[str(p) for p in scans],mode,'--poses',str(poses),export,str(output)]
            with patch.object(sys,'argv',args),patch.object(viewer,'Slider',slider),patch.object(viewer,'RadioButtons',radio),patch.object(viewer,'Button',button),patch.object(plt,'show',interact):viewer.main()
    def test_grid_callbacks(self):self.check_mode('--grid-map')
    def test_vector_callbacks(self):self.check_mode('--vector-map')

if __name__=='__main__':unittest.main()
