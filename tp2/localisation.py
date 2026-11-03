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
 out=[];reference_norm=(reference*reference).sum(1)
 for i in range(0,len(points),256):
  block=points[i:i+256]
  squared=(block*block).sum(1)[:,None]+reference_norm[None,:]-2*(block@reference.T)
  out.append(np.maximum(squared.min(1),0))
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
    def __init__(self,reference,resolution=.04):
        self.points=valid_scan(reference)
        self.resolution=resolution
        self.origin=np.floor((self.points.min(0)-.5)/resolution)*resolution
        high=self.points.max(0)+.5
        width,height=np.ceil((high-self.origin)/resolution).astype(int)
        ys,xs=np.indices((height,width))
        centers=self.origin+(np.column_stack([xs.ravel(),ys.ravel()])+.5)*resolution
        self.field=np.sqrt(nearest_squared(centers,self.points)).reshape(height,width)
    def residuals(self,points):return np.sqrt(nearest_squared(points,self.points))

    def fast_residuals(self,points):
        """Bilinear distance lookup for searching; exact points remain the reference."""
        coordinates=(points-self.origin)/self.resolution-.5
        ix=np.floor(coordinates[:,0]).astype(int);iy=np.floor(coordinates[:,1]).astype(int)
        h,w=self.field.shape;inside=(ix>=0)&(iy>=0)&(ix+1<w)&(iy+1<h)
        distances=np.full(len(points),1.)
        x=ix[inside];y=iy[inside];fx=coordinates[inside,0]-x;fy=coordinates[inside,1]-y
        field=self.field
        distances[inside]=(field[y,x]*(1-fx)*(1-fy)+field[y,x+1]*fx*(1-fy)+
                           field[y+1,x]*(1-fx)*fy+field[y+1,x+1]*fx*fy)
        return distances

def objective(reference,points,pose):
 d=reference.residuals(apply_pose(points,*pose))
 return float(np.mean(np.minimum(d,.6)**2))


def objective_batch(reference,points,poses,batch_size=16):
    """Score many candidate poses with one vectorized transformation per batch."""
    poses=np.asarray(poses,float);points=np.asarray(points,float)
    costs=np.empty(len(poses),float)
    for first in range(0,len(poses),batch_size):
        batch=poses[first:first+batch_size]
        radians=np.deg2rad(batch[:,2]);c=np.cos(radians)[:,None];s=np.sin(radians)[:,None]
        x=c*points[None,:,0]-s*points[None,:,1]+batch[:,None,0]
        y=s*points[None,:,0]+c*points[None,:,1]+batch[:,None,1]
        cloud=np.stack([x,y],axis=-1)
        residuals=getattr(reference,'fast_residuals',reference.residuals)
        d=residuals(cloud.reshape(-1,2)).reshape(len(batch),len(points))
        costs[first:first+len(batch)]=np.mean(np.minimum(d,.6)**2,axis=1)
    return costs

def _distinct_best(trials,count,translation_gap,angle_gap):
    """Keep different pose hypotheses instead of several samples of one minimum."""
    chosen=[]
    for candidate in sorted(trials,key=lambda item:item[0]):
        pose=candidate[1]
        if all(np.linalg.norm(pose[:2]-other[1][:2])>translation_gap or
               abs(wrap(pose[2]-other[1][2]))>angle_gap for other in chosen):
            chosen.append(candidate)
            if len(chosen)==count:break
    return chosen


def multiresolution(points,reference,initial):
    """Broad coarse search followed by local pose refinement on the same reference."""
    points=valid_scan(points);initial=np.asarray(initial,float)
    if initial.shape!=(3,) or not np.isfinite(initial).all():raise ValueError('Pose finie requise')
    evaluations=0
    # First pass covers +/-2.5 m and +/-100 degrees. Only ranking uses fewer points.
    coarse_points=points[::3]
    coarse=[]
    for dx in range(-5,6):
        for dy in range(-5,6):
            for da in range(-10,11):
                pose=initial+np.array([dx*.5,dy*.5,da*10.])
                pose[2]=wrap(pose[2]);coarse.append(pose)
    evaluations+=len(coarse)
    # Re-score many coarse minima using the complete query before choosing modes.
    coarse_scores=objective_batch(reference,coarse_points,coarse)
    coarse=np.asarray(coarse)
    shortlist=coarse[np.argsort(coarse_scores)[:120]]
    candidates=list(zip(objective_batch(reference,points,shortlist),shortlist))
    evaluations+=len(candidates)
    candidates=_distinct_best(candidates,8,.35,8.)
    for translation_step,angle_step,retain,gap_m,gap_deg in [
        (.15,3.,6,.12,2.5),(.04,1.,4,.035,.8),(.01,.25,3,.008,.2)
    ]:
        trials=[];seen=set()
        for _,center in candidates:
            for dx in range(-2,3):
                for dy in range(-2,3):
                    for da in range(-2,3):
                        pose=center+np.array([dx*translation_step,dy*translation_step,da*angle_step])
                        pose[2]=wrap(pose[2]);key=tuple(np.round(pose,7))
                        if key in seen:continue
                        seen.add(key);trials.append(pose);evaluations+=1
        scores=objective_batch(reference,points,trials)
        candidates=_distinct_best(list(zip(scores,trials)),retain,gap_m,gap_deg)
    if hasattr(reference,'fast_residuals'):
        candidates=[(objective(reference,points,pose),pose) for _,pose in candidates]
        candidates.sort(key=lambda item:item[0])
    cost,pose=candidates[0]
    return pose,dict(score=cost,evaluations=evaluations,coarse_hypotheses=8)

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

def coarse_icp(points,reference,initial):
    coarse,search_info=multiresolution(points,reference,initial)
    refined,icp_info=icp(points,reference,coarse)
    # Keep the better score in case ICP is drawn into a wrong local minimum.
    if icp_info['score']>search_info['score']:
        return coarse,dict(score=search_info['score'],evaluations=search_info['evaluations'],iterations=icp_info['iterations'])
    return refined,dict(score=icp_info['score'],evaluations=search_info['evaluations'],iterations=icp_info['iterations'])


METHODS={'grid_multiresolution':(GridReference,multiresolution),'vector_multiresolution':(VectorReference,multiresolution),'scan_coarse_icp':(ScanReference,coarse_icp)}
