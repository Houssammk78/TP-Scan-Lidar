"""TP2 : localisation sur grille, segments, et nuage de reference. Metres/degres."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tp1'/'LD06_Atelier'))
from geometry import apply_pose
from grid_map import build_grid
from vector_map import extract_segments

def wrap(angle):return (float(angle)+180)%360-180

def valid_scan(points):
 p=np.asarray(points,float)
 if p.ndim!=2 or p.shape[1]!=2:raise ValueError('Scan Nx2 requis')
 r=np.linalg.norm(p,axis=1);p=p[np.isfinite(p).all(1)&(r>=.15)&(r<=12)]
 if len(p)<5:raise ValueError('Au moins cinq points valides requis')
 return p

def nearest_squared(points,reference):
 out=[]
 for i in range(0,len(points),256):out.append(((points[i:i+256,None]-reference[None])**2).sum(2).min(1))
 return np.concatenate(out)

class GridReference:
    def __init__(self,reference,resolution=.06):
        self.grid=build_grid([reference],[[0,0,0]],resolution)
        yy,xx=np.where(self.grid.cells==100)
        if len(xx)==0:raise ValueError('Grille sans obstacle')
        obstacles=self.grid.origin+(np.column_stack([xx,yy])+.5)*resolution
        h,w=self.grid.cells.shape
        ys,xs=np.indices((h,w));centers=self.grid.origin+(np.column_stack([xs.ravel(),ys.ravel()])+.5)*resolution
        self.field=np.sqrt(nearest_squared(centers,obstacles)).reshape(h,w)
    def residuals(self,points):
        g=self.grid;ij=np.floor((points-g.origin)/g.resolution).astype(int);x,y=ij.T;h,w=g.cells.shape
        inside=(x>=0)&(y>=0)&(x<w)&(y<h);d=np.full(len(points),1.)
        d[inside]=self.field[y[inside],x[inside]]
        # Unknown cells inside the bounding box are not interpreted as free space.
        return d

class VectorReference:
    def __init__(self,reference):
        self.segments=np.asarray(extract_segments(reference,gap=.35,error=.045,min_points=5,min_length=.15))
        if len(self.segments)==0:raise ValueError('Carte sans segment extrait')
    def residuals(self,points):
        a=self.segments[:,0];v=self.segments[:,1]-a
        delta=points[:,None]-a[None];t=np.clip((delta*v).sum(2)/(v*v).sum(1),0,1)
        return np.sqrt(((delta-t[:,:,None]*v)**2).sum(2).min(1))

class ScanReference:
    def __init__(self,reference):self.points=valid_scan(reference)
    def residuals(self,points):return np.sqrt(nearest_squared(points,self.points))

def objective(reference,points,pose):
 d=reference.residuals(apply_pose(points,*pose))
 return float(np.mean(np.minimum(d,.6)**2))

def multiresolution(points,reference,initial):
    points=valid_scan(points);initial=np.asarray(initial,float)
    if initial.shape!=(3,) or not np.isfinite(initial).all():raise ValueError('Pose finie requise')
    # Bounded, progressively refined translation/angle search. Same settings for both maps.
    candidates=[(objective(reference,points,initial),initial.copy())];evaluations=1
    for translation_step,angle_step,radius in [(.5,10,2),(.15,3,2),(.04,1,2),(.01,.25,2)]:
        trials=[];seen=set()
        for _,center in candidates[:3]:
            for dx in range(-radius,radius+1):
                for dy in range(-radius,radius+1):
                    for da in range(-radius,radius+1):
                        pose=center+np.array([dx*translation_step,dy*translation_step,da*angle_step]);pose[2]=wrap(pose[2]);key=tuple(np.round(pose,7))
                        if key in seen:continue
                        seen.add(key);trials.append((objective(reference,points,pose),pose));evaluations+=1
        candidates=sorted(trials,key=lambda item:item[0])[:3]
    cost,pose=candidates[0];return pose,dict(score=cost,evaluations=evaluations)

def icp(points,reference,initial,max_iterations=70):
    source=valid_scan(points);target=reference.points;pose=np.asarray(initial,float).copy()
    if pose.shape!=(3,) or not np.isfinite(pose).all():raise ValueError('Pose finie requise')
    for iteration in range(max_iterations):
        transformed=apply_pose(source,*pose)
        ds=((transformed[:,None]-target[None])**2).sum(2);ids=ds.argmin(1);errors=ds[np.arange(len(source)),ids]
        keep=errors<=np.quantile(errors,.85)
        x=transformed[keep];y=target[ids[keep]];xc=x.mean(0);yc=y.mean(0)
        u,_,vt=np.linalg.svd((x-xc).T@(y-yc));R=vt.T@u.T
        if np.linalg.det(R)<0:vt[-1]*=-1;R=vt.T@u.T
        dt=yc-R@xc;angle=np.degrees(np.arctan2(R[1,0],R[0,0]));pose[:2]=R@pose[:2]+dt;pose[2]=wrap(pose[2]+angle)
        if np.linalg.norm(dt)<1e-5 and abs(angle)<1e-4:break
    return pose,dict(score=objective(reference,source,pose),iterations=iteration+1)

METHODS={'grid_multiresolution':(GridReference,multiresolution),'vector_multiresolution':(VectorReference,multiresolution),'scan_icp':(ScanReference,icp)}
