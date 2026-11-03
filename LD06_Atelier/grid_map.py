"""Grille ternaire : -1 inconnu, 0 libre, 100 occupe. Unites : metres."""
import json
from pathlib import Path
import numpy as np
from geometry import apply_pose


def bresenham(start,end):
    x,y=map(int,start);tx,ty=map(int,end)
    dx=abs(tx-x);dy=-abs(ty-y);sx=1 if x<tx else -1;sy=1 if y<ty else -1;err=dx+dy
    while True:
        yield x,y
        if x==tx and y==ty:break
        twice=2*err
        if twice>=dy:err+=dy;x+=sx
        if twice<=dx:err+=dx;y+=sy

class GridMap:
    def __init__(self,origin,size,resolution=.05):
        self.resolution=float(resolution);self.origin=np.asarray(origin,float)
        size=np.asarray(size,float)
        if not np.isfinite(self.resolution) or self.resolution<=0 or self.origin.shape!=(2,) or size.shape!=(2,) or not np.isfinite(self.origin).all() or not np.isfinite(size).all() or (size<=0).any():raise ValueError('Dimensions ou resolution invalides')
        shape=np.ceil(size/self.resolution).astype(int)
        if int(shape[0])*int(shape[1])>10_000_000:raise ValueError('Grille trop grande (maximum 10 millions de cellules)')
        self.cells=np.full((shape[1],shape[0]),-1,dtype=np.int16);self.scan_count=0

    @property
    def extent(self):
        x,y=self.origin;h,w=self.cells.shape;r=self.resolution
        return [x,x+w*r,y,y+h*r]

    def index(self,point):
        return tuple(np.floor((np.asarray(point)-self.origin)/self.resolution).astype(int))

    def contains(self,index):
        x,y=index;h,w=self.cells.shape
        return 0<=x<w and 0<=y<h

    def update(self,points,pose):
        p=np.asarray(points,float);pose=np.asarray(pose,float)
        if p.ndim!=2 or p.shape[1]!=2 or pose.shape!=(3,) or not np.isfinite(pose).all():raise ValueError('Scan ou pose invalide')
        origin=self.index(pose[:2])
        if not self.contains(origin):raise ValueError('Capteur hors de la grille')
        ranges=np.linalg.norm(p,axis=1);p=p[np.isfinite(p).all(1)&(ranges>=.15)&(ranges<=12)]
        free=set();occupied=set()
        for impact in apply_pose(p,*pose):
            end=self.index(impact)
            # A fixed-size map rejects out-of-map impacts rather than inventing a border obstacle.
            if not self.contains(end):continue
            ray=list(bresenham(origin,end));free.update(ray[:-1]);occupied.add(end)
        # Impacts take priority within a scan, independently of beam order.
        for x,y in free:self.cells[y,x]=0
        for x,y in occupied:self.cells[y,x]=100
        self.scan_count+=1
        return self

    def export(self,prefix):
        prefix=Path(prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
        np.savetxt(str(prefix)+'.csv',self.cells,fmt='%d',delimiter=';')
        np.savez_compressed(str(prefix)+'.npz',cells=self.cells,origin=self.origin,resolution=self.resolution,scan_count=self.scan_count)
        Path(str(prefix)+'.json').write_text(json.dumps(dict(resolution_m=self.resolution,origin_m=self.origin.tolist(),shape_rows_columns=list(self.cells.shape),scan_count=self.scan_count,states={'unknown':-1,'free':0,'occupied':100},row_order='Y croissant, ligne 0 en bas de la carte'),indent=2),encoding='utf-8')

    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as d:
            cells=d['cells'];r=float(d['resolution']);h,w=cells.shape
            obj=cls(d['origin'],[w*r,h*r],r)
            if not np.isin(cells,[-1,0,100]).all():raise ValueError('Etats de grille invalides')
            obj.cells=cells.copy();obj.scan_count=int(d['scan_count']);return obj


def build_grid(clouds,poses,resolution=.05):
    if len(clouds)!=len(poses) or not clouds:raise ValueError('Scans et poses requis')
    transformed=[np.asarray(pose[:2],float)[None,:] for pose in poses]
    for cloud,pose in zip(clouds,poses):
        cloud=np.asarray(cloud,float);r=np.linalg.norm(cloud,axis=1)
        valid=cloud[np.isfinite(cloud).all(1)&(r>=.15)&(r<=12)]
        transformed.append(apply_pose(valid,*pose))
    points=np.vstack(transformed);low=np.floor((points.min(0)-.5)/resolution)*resolution;high=points.max(0)+.5
    grid=GridMap(low,high-low,resolution)
    for cloud,pose in zip(clouds,poses):grid.update(cloud,pose)
    return grid
