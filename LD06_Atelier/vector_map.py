"""Primitives vectorielles 2D. Distances en metres, angles en degres."""
import csv
import numpy as np

EPS = 1e-8  # tolerance spatiale (m) ; tests parametriques convertis par longueur

def segment(value):
    s=np.asarray(value,dtype=float)
    if s.shape!=(2,2) or not np.isfinite(s).all() or np.linalg.norm(s[1]-s[0])<=EPS:
        raise ValueError('Segment non fini ou de longueur nulle')
    return s

def cross(a,b):
    return float(a[0]*b[1]-a[1]*b[0])

def angle_between(a,b):
    a,b=segment(a),segment(b)
    u=a[1]-a[0];v=b[1]-b[0]
    return float(np.degrees(np.arccos(np.clip(abs(np.dot(u,v))/(np.linalg.norm(u)*np.linalg.norm(v)),0,1))))

def point_distance(p,s):
    s=segment(s);v=s[1]-s[0];t=np.clip(np.dot(p-s[0],v)/np.dot(v,v),0,1)
    return float(np.linalg.norm(p-s[0]-t*v))

def intersection(a,b,tol=EPS):
    """Intersection unique sur les deux segments ; colineaires -> None."""
    a,b=segment(a),segment(b);u=a[1]-a[0];v=b[1]-b[0]
    lu,lv=np.linalg.norm(u),np.linalg.norm(v);den=cross(u,v)
    if abs(den)<=1e-12*lu*lv:return None
    delta=b[0]-a[0];t=cross(delta,v)/den;q=cross(delta,u)/den
    if -tol/lu<=t<=1+tol/lu and -tol/lv<=q<=1+tol/lv:
        return a[0]+np.clip(t,0,1)*u
    return None

def cut_longest(a,b,tol=EPS):
    """Coupe a seulement si intersection interieure ; egalite -> premier point."""
    a=segment(a);p=intersection(a,b,tol)
    if p is None:return a.copy()
    first=np.linalg.norm(p-a[0]);second=np.linalg.norm(a[1]-p)
    if min(first,second)<=tol:return a.copy()
    return np.array([a[0],p]) if first>=second-tol else np.array([p,a[1]])

def are_close(a,b,angle_deg=8,distance=.15,gap=.25):
    a,b=segment(a),segment(b)
    if angle_between(a,b)>angle_deg:return False
    u=(a[1]-a[0])/np.linalg.norm(a[1]-a[0]);v=(b[1]-b[0])/np.linalg.norm(b[1]-b[0])
    # Symmetric supporting-line distance prevents merging displaced walls.
    separation=max(abs(cross(u,b.mean(0)-a.mean(0))),abs(cross(v,a.mean(0)-b.mean(0))))
    if separation>distance:return False
    aa=sorted(a@u);bb=sorted(b@u)
    return max(aa[0]-bb[1],bb[0]-aa[1],0)<=gap

def fit_segment(points):
    p=np.asarray(points,float);center=p.mean(0);_,_,vt=np.linalg.svd(p-center,full_matrices=False)
    axis=vt[0];t=(p-center)@axis
    return np.array([center+axis*t.min(),center+axis*t.max()])

def merge_segments(a,b,**thresholds):
    if not are_close(a,b,**thresholds):return None
    return fit_segment(np.vstack([a,b]))

def extract_segments(points,gap=.32,error=.06,min_points=5,min_length=.2):
    """Continuite d'acquisition puis split-and-fit par distance a la droite."""
    p=np.asarray(points,float);valid=np.isfinite(p).all(1)&(np.linalg.norm(p,axis=1)>=.15)&(np.linalg.norm(p,axis=1)<=12)
    groups=[];start=0
    # Invalid measurements split clusters rather than joining across missing data.
    for i in range(len(p)):
        if not valid[i] or (i>start and np.linalg.norm(p[i]-p[i-1])>gap):
            if i>start:groups.append(p[start:i])
            start=i+1 if not valid[i] else i
    if start<len(p):groups.append(p[start:])
    out=[]
    def split(q):
        if len(q)<min_points:return
        fitted=fit_segment(q);u=fitted[1]-fitted[0];length=np.linalg.norm(u)
        if length<=EPS:return
        distances=np.abs((q-fitted[0])[:,0]*u[1]-(q-fitted[0])[:,1]*u[0])/length
        chord=q[-1]-q[0];chord_length=np.linalg.norm(chord)
        if chord_length>EPS:
            split_dist=np.abs((q-q[0])[:,0]*chord[1]-(q-q[0])[:,1]*chord[0])/chord_length
        else:split_dist=np.linalg.norm(q-q[0],axis=1)
        k=int(split_dist.argmax())
        if distances[k]>error:
            # Do not accept a badly fitted cluster just because a child is small.
            k=min(max(k,1),len(q)-2);split(q[:k+1]);split(q[k:]);return
        if length>=min_length:out.append(fitted)
    for q in groups:split(q)
    return out

class VectorMap:
    def __init__(self):
        self.features=[];self.step=0

    def update(self,local_points,pose,clear_crossed=True):
        from geometry import apply_pose
        self.step+=1
        local=np.asarray(local_points,float);global_points=apply_pose(local,*pose)
        fresh=[apply_pose(s,*pose) for s in extract_segments(local)]
        # Free-space rays stop before impacts to avoid erasing observed surfaces.
        if clear_crossed:
            origin=np.asarray(pose[:2],float)
            valid=np.isfinite(local).all(1)&(np.linalg.norm(local,axis=1)>=.15)&(np.linalg.norm(local,axis=1)<=12)
            for impact in global_points[valid]:
                delta=impact-origin;length=np.linalg.norm(delta)
                if length<=.2:continue
                ray=np.array([origin,impact-delta*.15/length])
                kept=[]
                for feature in self.features:
                    feature=dict(feature);feature['segment']=cut_longest(feature['segment'],ray)
                    if np.linalg.norm(np.diff(feature['segment'],axis=0))>=.2:kept.append(feature)
                self.features=kept
        for s in fresh:
            count=1;remaining=list(self.features);self.features=[]
            # Repeat after fusion, as an extended segment may match another feature.
            changed=True
            while changed:
                changed=False;rest=[]
                for f in remaining:
                    merged=merge_segments(s,f['segment'])
                    if merged is None:rest.append(f)
                    else:s=merged;count+=f['observations'];changed=True
                remaining=rest
            self.features=remaining+[dict(segment=s,observations=count,last_seen=self.step)]
        return self.features

    def export(self,path):
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter=';');w.writerow(['x1_m','y1_m','x2_m','y2_m','observations','last_seen'])
            for feature in self.features:w.writerow([*feature['segment'].ravel(),feature['observations'],feature['last_seen']])
