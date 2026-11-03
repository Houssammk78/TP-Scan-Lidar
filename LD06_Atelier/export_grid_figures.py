"""Genere les illustrations de la grid map avec les poses enregistrees."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import numpy as np
from geometry import load_scan
from grid_map import build_grid,GridMap

def main():
    here=Path(__file__).resolve().parent;root=here.parent
    paths=[root/'scan_20261102_170811_045727.csv',root/'scan_20261102_170911_554109.csv']
    saved=json.loads((here/'poses.json').read_text(encoding='utf-8'))
    poses=[saved.get(str(p.resolve()), saved.get(p.name)) for p in paths];clouds=[load_scan(p) for p in paths]
    final=build_grid(clouds,poses,.05);final.export(here/'grid_map')
    first=GridMap(final.origin,np.array(final.cells.shape[::-1])*final.resolution,final.resolution);first.update(clouds[0],poses[0])
    cmap=ListedColormap(['#8d6e63','#81c784','#d32f2f']);norm=BoundaryNorm([-1.5,-.5,50,100.5],3)
    def draw(ax,grid,title,count):
        ax.imshow(grid.cells,origin='lower',extent=grid.extent,cmap=cmap,norm=norm,interpolation='nearest')
        for i,pose in enumerate(poses[:count]):ax.plot(pose[0],pose[1],'+',color='#1565ff',ms=11,mew=2)
        ax.set(xlabel='X (m)',ylabel='Y (m)',title=title,aspect='equal')
    legend=[Patch(facecolor=c,edgecolor='#555',label=l) for c,l in [('#8d6e63','Inconnu'),('#81c784','Libre'),('#d32f2f','Occupe')]]
    legend.append(Line2D([],[],marker='+',linestyle='none',color='#1565ff',markersize=10,label='Position du LiDAR'))
    fig,ax=plt.subplots(figsize=(10,10));draw(ax,final,'Chambre - grid map estimee (cellules de 5 cm)',2)
    ax.legend(handles=legend,loc='upper left');fig.text(.5,.02,'Deux scans reels, poses estimees. Croix : positions du capteur.',ha='center');fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(root/'grid_map_finale.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,7));draw(axes[0],first,'Apres le scan 1',1);draw(axes[1],final,'Apres les scans 1 et 2',2);axes[0].legend(handles=legend,loc='upper left');fig.tight_layout();fig.savefig(root/'grid_map_progression.png',dpi=160);plt.close(fig)
    print('Grille :',final.cells.shape,'; scans :',final.scan_count)
    print('Cellules par etat :',dict(zip(*np.unique(final.cells,return_counts=True))))

if __name__=='__main__':main()
