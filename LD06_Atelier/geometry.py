"""Lecture CSV (mm), sans inversion de Y ; poses en m?tres et degr?s."""
import csv
import numpy as np

def load_scan(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        sample=f.read(4096);f.seek(0)
        reader=csv.DictReader(f, delimiter=';' if ';' in sample.splitlines()[0] else ',')
        names=reader.fieldnames or []
        cols=next((pair for pair in [('x_corrige_mm','y_corrige_mm'),('x_mm','y_mm'),('x_lib_mm','y_lib_mm')] if all(k in names for k in pair)),None)
        if cols is None: raise ValueError('Colonnes X/Y introuvables : '+str(path))
        points=np.array([[float(r[k].replace(',','.'))/1000 for k in cols] for r in reader])
    if points.ndim!=2 or points.shape[1]!=2 or not np.isfinite(points).all(): raise ValueError('Scan vide ou coordonn?es invalides')
    return points

def apply_pose(points,x,y,angle):
    t=np.deg2rad(angle);r=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
    return points@r.T+np.array([x,y])
