"""Raycasting dans un environnement asymetrique avec poses exactes et bruit independant."""
import numpy as np

def scene():
 polygon=np.array([[-3,-2],[5,-2],[5,4],[2,4],[2,6],[-3,6],[-3,-2]],float)
 segments=list(np.stack([polygon[:-1],polygon[1:]],axis=1))
 for x0,y0,x1,y1 in [(-1,2,0,3),(3,.6,3.6,1.6)]:
  p=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]])
  segments.extend(np.stack([p[:-1],p[1:]],axis=1))
 return np.asarray(segments)

def raycast(segments,pose,seed=1,count=540,noise=.008):
 rng=np.random.default_rng(seed);origin=np.asarray(pose[:2]);angles=np.linspace(0,2*np.pi,count,endpoint=False)
 world=angles+np.deg2rad(pose[2]);directions=np.column_stack([np.cos(world),np.sin(world)])
 a=segments[:,0];v=segments[:,1]-a;delta=a-origin
 cross=lambda x,y:x[...,0]*y[...,1]-x[...,1]*y[...,0]
 den=cross(directions[:,None],v[None]);safe=np.where(abs(den)>1e-12,den,np.nan)
 t=cross(delta,v)[None,:]/safe;q=cross(delta[None],directions[:,None])/safe
 valid=(t>.15)&(q>=0)&(q<=1)&np.isfinite(t)
 ranges=np.where(valid,t,np.inf).min(1);mask=ranges<12
 ranges=ranges[mask]+rng.normal(0,noise,mask.sum())
 return np.column_stack([np.cos(angles[mask])*ranges,np.sin(angles[mask])*ranges])
