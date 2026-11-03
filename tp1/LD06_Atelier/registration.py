"""Recalage multi-departs robuste ; unites en metres."""
import numpy as np

def rotation(deg):
 t=np.deg2rad(deg);return np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])

def distances(a,b):return ((a[:,None]-b[None])**2).sum(2)

def fit(source,target,R,T,n=35):
 for _ in range(n):
  p=source@R.T+T;ds=distances(p,target);ids=ds.argmin(1);e=ds[np.arange(len(p)),ids]
  keep=e<=np.quantile(e,.65);x=p[keep];y=target[ids[keep]];xc=x.mean(0);yc=y.mean(0)
  u,_,vt=np.linalg.svd((x-xc).T@(y-yc));dr=vt.T@u.T
  if np.linalg.det(dr)<0:vt[-1]*=-1;dr=vt.T@u.T
  dt=yc-xc@dr.T;R=dr@R;T=T@dr.T+dt
 return R,T

def score(source,target,R,T,cap=.4):
 ds=distances(source@R.T+T,target)
 return float((np.minimum(ds.min(0),cap**2).mean()+np.minimum(ds.min(1),cap**2).mean())/2)

def register(source,target):
 x=source[::4];y=target[::4];candidates=[]
 for angle in range(0,360,10):
  r=rotation(angle);center=np.median(y,axis=0)-np.median(x@r.T,axis=0)
  for dx in [-4,0,4]:
   for dy in [-4,0,4]:
    R,T=fit(x,y,r.copy(),center+[dx,dy],30)
    candidates.append((score(x,y,R,T,.6),R,T))
 candidates.sort(key=lambda v:v[0]);refined=[]
 for _,R,T in candidates[:18]:
  R,T=fit(source,target,R,T,65);refined.append((score(source,target,R,T),R,T))
 refined.sort(key=lambda v:v[0]);return refined[0],refined
