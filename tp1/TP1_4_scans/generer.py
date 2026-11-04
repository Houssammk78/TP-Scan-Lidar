"""Genere les cartes individuelles et fusionnees des quatre scans."""
import csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'LD06_Atelier'))
from geometry import load_scan,apply_pose
from grid_map import build_grid,GridMap
from vector_map import VectorMap,extract_segments,intersection

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'resultats'

def draw_grid(ax,g,title,poses):
 ax.imshow(g.cells,origin='lower',extent=g.extent,cmap=ListedColormap(['#8d6e63','#81c784','#d32f2f']),norm=BoundaryNorm([-1.5,-.5,50,100.5],3),interpolation='nearest')
 for i,p in enumerate(poses,1):
  ax.plot(*p[:2],'+',c='#1565ff',ms=11);ax.annotate(str(i),p[:2],xytext=(5,5),textcoords='offset points',color='#003399')
 ax.set(xlabel='X (m)',ylabel='Y (m)',title=title,aspect='equal')
 ax.legend(handles=[Patch(color=c,label=l) for c,l in [('#8d6e63','Inconnu'),('#81c784','Libre'),('#d32f2f','Occupe')]],loc='upper right',fontsize=8)

def draw_vectors(ax,points,mapping,title,poses):
 ax.scatter(*points.T,c='#9aa6a9',s=6,alpha=.5,label=f'Mesures ({len(points)})')
 segs=[f['segment'] for f in mapping.features]
 ax.add_collection(LineCollection(segs,colors='#20638b',linewidths=2.2,label=f'Segments ({len(segs)})'))
 crossings=[]
 for i,a in enumerate(segs):
  for b in segs[i+1:]:
   p=intersection(a,b)
   if p is not None and all(np.linalg.norm(p-q)>.03 for q in crossings):crossings.append(p)
 if crossings:ax.scatter(*np.asarray(crossings).T,marker='x',c='#dc9137',s=28,label='Intersections',zorder=4)
 for i,p in enumerate(poses,1):
  ax.plot(*p[:2],'+',c='#c34c48',ms=11);ax.annotate(f'S{i}',p[:2],xytext=(5,5),textcoords='offset points',color='#a23232')
 ax.set(xlabel='X (m)',ylabel='Y (m)',title=title,aspect='equal');ax.grid(alpha=.2);ax.autoscale_view();ax.legend(fontsize=8,loc='upper right')

def main():
 saved=json.loads((ROOT/'poses.json').read_text());clouds=[load_scan(ROOT/'data'/f'scan{i}.csv') for i in range(1,5)];poses=[saved[f'scan{i}.csv'] for i in range(1,5)]
 OUT.mkdir(exist_ok=True);colors=['#1976d2','#ed8b20','#2e7d32','#8e24aa']
 fig,ax=plt.subplots(figsize=(11,10));global_clouds=[]
 for i,(c,p,col) in enumerate(zip(clouds,poses,colors),1):
  pts=apply_pose(c,*p);global_clouds.append(pts);ax.scatter(*pts.T,s=8,c=col,label=f'Scan {i} ({len(c)} points)');ax.plot(*p[:2],'+',c=col,ms=12)
 ax.set(xlabel='X (m)',ylabel='Y (m)',title='Fusion de quatre scans - recalage estime',aspect='equal');ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(OUT/'fusion_4_scans.png',dpi=170);plt.close(fig)
 allpoints=np.vstack(global_clouds)
 # Scans 3 et 4 couvrent la meme enveloppe avec un fort recouvrement.
 # Ces bornes de points ne sont pas une mesure physique des murs.
 stable=np.vstack(global_clouds[2:4]);low=stable.min(axis=0);high=stable.max(axis=0)
 (OUT/'dimensions_estimees.json').write_text(json.dumps({
  'source_scans':['scan3.csv','scan4.csv'],
  'method':'bornes min/max des impacts alignes des scans 3 et 4',
  'x_min_m':float(low[0]),'x_max_m':float(high[0]),
  'y_min_m':float(low[1]),'y_max_m':float(high[1]),
  'extent_x_m':float(high[0]-low[0]),'extent_y_m':float(high[1]-low[1]),
  'note':'Emprise observee et estimee ; pas une mesure terrain independante.'
 },indent=2,ensure_ascii=False),encoding='utf-8')
 with (OUT/'fusion_4_scans.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f,delimiter=';');w.writerow(['scan','point_index','angle_deg_local','dist_mm_local','intensity','x_local_mm','y_local_mm','x_corrige_mm','y_corrige_mm'])
  for i,(file,pts) in enumerate(zip([ROOT/'data'/f'scan{i}.csv' for i in range(1,5)],global_clouds),1):
   with file.open(encoding='utf-8-sig') as source:rows=list(csv.DictReader(source))
   for r,p in zip(rows,pts):w.writerow([i,r['point_index'],*[r[k].replace('.',',') for k in ['angle_deg','dist_mm','intensity','x_lib_mm','y_lib_mm']],*[str(round(float(v)*1000,2)).replace('.',',') for v in p]])
 vector=VectorMap();figg,axg=plt.subplots(2,2,figsize=(14,12));figv,axv=plt.subplots(2,2,figsize=(14,12))
 for i,(c,p) in enumerate(zip(clouds,poses),1):
  localgrid=build_grid([c],[[0,0,0]],.05);localgrid.export(OUT/f'grid_scan{i}')
  localvector=VectorMap();localvector.update(c,[0,0,0]);localvector.export(OUT/f'vectorielle_scan{i}.csv')
  draw_grid(axg.flat[i-1],localgrid,f'Scan {i} - repere local',[[0,0,0]])
  draw_vectors(axv.flat[i-1],c,localvector,f'Scan {i} - repere local',[[0,0,0]])
  for kind,func in [('grid',draw_grid),('vectorielle',draw_vectors)]:
   f,a=plt.subplots(figsize=(9,9))
   if kind=='grid':func(a,localgrid,f'Scan {i} - occupation',[[0,0,0]])
   else:func(a,c,localvector,f'Scan {i} - segments',[[0,0,0]])
   f.tight_layout();f.savefig(OUT/f'{kind}_scan{i}.png',dpi=150);plt.close(f)
  vector.update(c,p,clear_crossed=False)
 figg.tight_layout();figg.savefig(OUT/'grilles_individuelles.png',dpi=150);plt.close(figg)
 figv.tight_layout();figv.savefig(OUT/'vectorielles_individuelles.png',dpi=150);plt.close(figv)
 vector.export(OUT/'carte_vectorielle.csv')
 fig,ax=plt.subplots(figsize=(12,11));draw_vectors(ax,allpoints,vector,'Carte vectorielle - fusion de quatre scans',poses)
 fig.text(.5,.015,'Poses estimees. Hauteur declaree par utilisateur : 1,90 m pour les quatre scans.',ha='center',fontsize=9)
 fig.tight_layout(rect=[0,.035,1,1]);fig.savefig(OUT/'carte_vectorielle.png',dpi=170);plt.close(fig)
 grid=build_grid(clouds,poses,.05);grid.export(OUT/'grid_map')
 fig,ax=plt.subplots(figsize=(12,11));draw_grid(ax,grid,'Carte occupation - quatre scans, cellules 5 cm',poses);fig.tight_layout();fig.savefig(OUT/'grid_map_finale.png',dpi=170);plt.close(fig)
 # Same map extent, cumulative updates with reference scan first.
 h,w=grid.cells.shape;progress=GridMap(grid.origin,[w*.05,h*.05],.05)
 fig,axes=plt.subplots(2,2,figsize=(14,12));order=[0,1,2,3]
 for step,idx in enumerate(order):
  progress.update(clouds[idx],poses[idx]);draw_grid(axes.flat[step],progress,f'{step+1} scan(s) integre(s)',[])
 fig.tight_layout();fig.savefig(OUT/'grid_map_progression.png',dpi=150);plt.close(fig)
 assert np.isin(grid.cells,[-1,0,100]).all()
 with (OUT/'fusion_4_scans.csv').open(encoding='utf-8-sig') as f:assert len(list(csv.DictReader(f,delimiter=';')))==sum(map(len,clouds))
 print(f'{len(allpoints)} mesures, {len(vector.features)} segments consolides, grille {grid.cells.shape}',flush=True)

if __name__=='__main__':main()
