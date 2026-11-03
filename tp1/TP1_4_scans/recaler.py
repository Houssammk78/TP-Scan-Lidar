from pathlib import Path
import sys,json,time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'LD06_Atelier'))
from geometry import load_scan
from registration import register,distances
root=Path(__file__).resolve().parent
clouds=[load_scan(root/'data'/f'scan{i}.csv') for i in range(1,5)]
valid=[p[(np.linalg.norm(p,axis=1)>=.15)&(np.linalg.norm(p,axis=1)<=12)] for p in clouds]
poses={'scan3.csv':[0.,0.,0.]};metrics={}
for i in [0,1,3]:
 start=time.perf_counter();(cost,R,T),candidates=register(valid[i],valid[2]);angle=float(np.degrees(np.arctan2(R[1,0],R[0,0])))
 name=f'scan{i+1}.csv';poses[name]=[*T.tolist(),angle]
 ds=distances(valid[i]@R.T+T,valid[2]);metrics[name]=dict(capped_rms_m=float(np.sqrt(cost)),source_within_20cm=float((ds.min(1)<.2**2).mean()),reference_within_20cm=float((ds.min(0)<.2**2).mean()),seconds=time.perf_counter()-start)
 print(name,poses[name],metrics[name],flush=True)
 (root/'poses.json').write_text(json.dumps(poses,indent=2),encoding='utf-8')
 (root/'resultats'/'alignement.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
