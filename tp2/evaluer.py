"""Protocole commun : references construites sans les scans de test."""
import argparse,csv,json,time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from localisation import METHODS,valid_scan,wrap
from simulation import scene,raycast
from geometry import load_scan,apply_pose

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'resultats'
OFFSETS=[(0,0,0),(.25,0,5),(-.25,.15,-5),(.5,-.25,10),(-.5,.3,-10),(.9,.5,20),(-.9,-.5,-20),(1.6,-1.1,35),(-2,1.4,-45),(0,0,90)]
POSITION_THRESHOLD=.2;ANGLE_THRESHOLD=5.

def csv_save(path,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
 with path.with_name(path.stem+'_Excel_FR.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');w.writeheader()
  for row in rows:
   converted={}
   for key,value in row.items():
    if value is None:converted[key]='';continue
    try:float(value);converted[key]=str(value).replace('.',',')
    except (ValueError,TypeError):converted[key]=value
   w.writerow(converted)

def prepare(reference):
 prepared={};times={}
 for name,(cls,_) in METHODS.items():
  start=time.perf_counter();prepared[name]=cls(reference);times[name]=time.perf_counter()-start
 return prepared,times


def read_measured_poses(path):
 """Independent robot measurements; blank rows intentionally mean unknown."""
 measured={}
 with path.open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f,delimiter=';'):
   label=row['scan'].strip()
   fields=['x_m','y_m','angle_deg','uncertainty_position_m','uncertainty_angle_deg']
   values=[row[key].strip().replace(',','.') for key in fields]
   if not any(values):continue
   if not all(values):raise ValueError(f'Mesure incomplete pour {label}: pose et incertitudes requises')
   numbers=np.array([float(value) for value in values])
   if not np.isfinite(numbers).all() or (numbers[3:]<0).any():raise ValueError(f'Mesure invalide pour {label}')
   if label in measured:raise ValueError(f'Scan mesure deux fois: {label}')
   measured[label]=dict(pose=numbers[:3].tolist(),uncertainty_position_m=float(numbers[3]),uncertainty_angle_deg=float(numbers[4]))
 return measured


def evaluate(dataset,reference,queries,offsets,truths=None):
 prepared,times=prepare(reference);rows=[];illustrations={}
 for qi,(label,query) in enumerate(queries.items()):
  # Identical angular subsampling supplied to every method.
  query=valid_scan(query)[::3]
  truth=None if truths is None else truths.get(label)
  center=np.array(truth,float) if dataset=='simulation' else np.zeros(3)
  for trial,offset in enumerate(offsets):
   initial=center+offset
   for name,(_,solver) in METHODS.items():
    start=time.perf_counter();pose,info=solver(query,prepared[name],initial);seconds=time.perf_counter()-start
    if truth is not None:
     pe=float(np.linalg.norm(pose[:2]-truth[:2]));ae=abs(wrap(pose[2]-truth[2]));success=pe<=POSITION_THRESHOLD and ae<=ANGLE_THRESHOLD
    else:pe=ae=success=None
    rows.append(dict(dataset=dataset,scan=label,trial=trial,method=name,initial_x=initial[0],initial_y=initial[1],initial_angle=initial[2],estimated_x=pose[0],estimated_y=pose[1],estimated_angle=pose[2],position_error_m=pe,angle_error_deg=ae,success=success,reference_uncertainty_position_m=None,reference_uncertainty_angle_deg=None,seconds=seconds,reference_build_seconds=times[name],residual_rms_capped_m=float(np.sqrt(info['score'])),points_tested=len(query)))
    if trial==0:illustrations[(label,name)]=(query,pose)
  print(dataset,label,'termine',flush=True)
 return rows,prepared,illustrations

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--mesures',type=Path,default=ROOT/'references_mesurees.csv',help='Poses terrain et incertitudes mesurees independamment')
 args=parser.parse_args()
 OUT.mkdir(exist_ok=True)
 shapes=scene();reference=raycast(shapes,[0,0,0],seed=11)
 truths={'simulation_B1':[.437,.127,4.3],'simulation_B2':[-.367,.283,-6.4],
         'simulation_B3':[1.1,-.7,12.], 'simulation_B4':[-.8,.95,-12.],
         'simulation_B5':[.2,1.3,25.], 'simulation_B6':[1.5,1.,-22.]}
 queries={k:raycast(shapes,p,seed=20+i) for i,(k,p) in enumerate(truths.items())}
 np.savez_compressed(OUT/'simulation.npz',segments=shapes,reference=reference,**queries)
 rows,refs,illustrations=evaluate('simulation',reference,queries,OFFSETS,truths)
 refs['grid_multiresolution'].grid.export(OUT/'reference_grid_simulation')
 np.savetxt(OUT/'reference_segments_simulation.csv',refs['vector_multiresolution'].segments.reshape(-1,4),delimiter=';',header='x1;y1;x2;y2',comments='')
 fig,axes=plt.subplots(1,3,figsize=(15,6))
 for ax,name in zip(axes,METHODS):
  query,pose=illustrations[('simulation_B1',name)];actual=apply_pose(query,*truths['simulation_B1']);estimated=apply_pose(query,*pose)
  ax.scatter(*reference.T,c='gray',s=5,label='Reference independante');ax.scatter(*actual.T,c='#2e7d32',s=7,label='Pose exacte');ax.scatter(*estimated.T,c='#1976d2',s=5,label='Pose estimee');ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_title(name);ax.legend(fontsize=7)
 fig.tight_layout();fig.savefig(OUT/'simulation_localisation.png',dpi=150);plt.close(fig)
 # A_01 only trains all references; A_02/A_03 and B scans are held out.
 adir=ROOT/'acquisitions/position_A_20261103_120212';bdir=ROOT/'acquisitions/position_B_20261103_120333'
 real_reference=valid_scan(load_scan(adir/'A_01.csv'))
 real_queries={p.stem:load_scan(p) for p in [adir/'A_02.csv',adir/'A_03.csv',bdir/'B_01.csv',bdir/'B_02.csv',bdir/'B_03.csv']}
 measurements=read_measured_poses(args.mesures)
 unexpected=set(measurements)-set(real_queries)
 if unexpected:raise ValueError(f'Mesures pour scans inconnus: {sorted(unexpected)}')
 real_truths={label:entry['pose'] for label,entry in measurements.items()}
 realrows,realrefs,realplots=evaluate('reel',real_reference,real_queries,OFFSETS[:5],real_truths)
 for row in realrows:
  measured=measurements.get(row['scan'])
  if measured:
   row['reference_uncertainty_position_m']=measured['uncertainty_position_m']
   row['reference_uncertainty_angle_deg']=measured['uncertainty_angle_deg']
 realrefs['grid_multiresolution'].grid.export(OUT/'reference_grid_reelle')
 csv_save(OUT/'essais.csv',rows+realrows)
 summaries=[]
 for dataset,table in [('simulation',rows),('reel',realrows)]:
  for name in METHODS:
   selected=[r for r in table if r['method']==name]
   known=[r for r in selected if r['position_error_m'] is not None]
   summaries.append(dict(dataset=dataset,method=name,trials=len(selected),trials_with_ground_truth=len(known),position_error_mean_m=float(np.mean([r['position_error_m'] for r in known])) if known else None,angle_error_mean_deg=float(np.mean([r['angle_error_deg'] for r in known])) if known else None,success_rate=float(np.mean([r['success'] for r in known])) if known else None,median_seconds=float(np.median([r['seconds'] for r in selected])),mean_residual_rms_capped_m=float(np.mean([r['residual_rms_capped_m'] for r in selected]))))
 csv_save(OUT/'synthese.csv',summaries)
 repeatability=[]
 for method in METHODS:
  for group in ['A','B']:
   selected=[r for r in realrows if r['method']==method and r['trial']==0 and r['scan'].startswith(group+'_')]
   poses=np.array([[r['estimated_x'],r['estimated_y'],r['estimated_angle']] for r in selected],float)
   angles=np.rad2deg(np.unwrap(np.deg2rad(poses[:,2])))
   repeatability.append(dict(method=method,position=group,scans=len(selected),mean_x_m=float(poses[:,0].mean()),mean_y_m=float(poses[:,1].mean()),mean_angle_deg=float(wrap(angles.mean())),std_x_m=float(poses[:,0].std(ddof=1)),std_y_m=float(poses[:,1].std(ddof=1)),std_angle_deg=float(angles.std(ddof=1))))
 csv_save(OUT/'repetabilite_reelle.csv',repeatability)
 report=dict(success_thresholds=dict(position_m=POSITION_THRESHOLD,angle_deg=ANGLE_THRESHOLD),simulation_poses=truths,initial_offsets=OFFSETS,random_seeds=[11,*range(20,20+len(truths))],summary=summaries,real_ground_truth=dict(available=bool(measurements),measurements=measurements,note='Poses terrain et incertitudes fournies independamment; lignes vides non evaluees.' if measurements else 'Aucun deplacement ou angle mesure. Erreurs reelles et taux de reussite terrain non calculables.'),real_reference='A_01 uniquement',query_subsampling='1 point sur 3 apres filtre, identique pour chaque methode',repeatability='Ecart type entre acquisitions distinctes depuis une meme position supposee; ne mesure pas la justesse physique.')
 (OUT/'protocole_et_resultats.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 fig,axes=plt.subplots(1,3,figsize=(15,4));names=list(METHODS)
 for ax,key,title in zip(axes,['position_error_m','angle_error_deg','seconds'],['Erreur position (m)','Erreur angulaire (degres)','Temps de calcul (s)']):
  ax.boxplot([[r[key] for r in rows if r['method']==n] for n in names],tick_labels=['Grille','Segments','ICP'],showmeans=True);ax.set_title(title);ax.grid(alpha=.2)
 fig.tight_layout();fig.savefig(OUT/'comparaison_simulation.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5))
 for name in names:
  rates=[np.mean([r['success'] for r in rows if r['method']==name and r['trial']==t])*100 for t in range(len(OFFSETS))]
  ax.plot(range(len(OFFSETS)),rates,'o-',label=name)
 ax.set(xticks=range(len(OFFSETS)),xlabel='Initialisation (voir tableau offsets)',ylabel='Reussite (%)',ylim=(-5,105),title=f'Sensibilite a la pose initiale - {len(truths)} scans simules par initialisation');ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(OUT/'sensibilite_initialisation.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(15,6))
 for ax,name in zip(axes,names):
  ax.scatter(*real_reference.T,s=7,c='gray',label='A_01 reference')
  for label,color in [('A_02','#1976d2'),('B_01','#ed8b20')]:
   query,pose=realplots[(label,name)];p=apply_pose(query,*pose);ax.scatter(*p.T,s=7,c=color,label=label)
  ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_title(name);ax.legend(fontsize=8)
 fig.suptitle('Scans reels - initialisation commune (0,0,0) ; poses non mesurees');fig.tight_layout();fig.savefig(OUT/'localisation_reelle.png',dpi=160);plt.close(fig)
 assert len(rows)==len(truths)*len(OFFSETS)*len(METHODS) and len(realrows)==len(real_queries)*5*len(METHODS)
 print(json.dumps(summaries,indent=2),flush=True)

if __name__=='__main__':main()
