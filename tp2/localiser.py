"""Essai individuel depuis une reference CSV et une pose initiale explicite."""
import argparse,json,time
from pathlib import Path
from localisation import METHODS,valid_scan
from geometry import load_scan

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--reference',type=Path,required=True);p.add_argument('--scan',type=Path,required=True)
 p.add_argument('--method',choices=METHODS,required=True);p.add_argument('--initial',nargs=3,type=float,default=[0,0,0],metavar=('X','Y','ANGLE'))
 p.add_argument('--output',type=Path,default=Path('pose_estimee.json'))
 a=p.parse_args();reference=valid_scan(load_scan(a.reference));query=valid_scan(load_scan(a.scan))[::3]
 cls,solver=METHODS[a.method];start=time.perf_counter();model=cls(reference);build=time.perf_counter()-start
 start=time.perf_counter();pose,info=solver(query,model,a.initial);elapsed=time.perf_counter()-start
 report=dict(method=a.method,reference=str(a.reference),scan=str(a.scan),initial=a.initial,pose_xy_m_angle_deg=pose.tolist(),build_seconds=build,solve_seconds=elapsed,diagnostics=info,ground_truth=None)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
