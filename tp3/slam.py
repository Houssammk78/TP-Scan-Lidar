"""TP3 : recalage de scans réels puis mise à jour progressive de deux cartes.

Lancer depuis la racine du dépôt : python tp3/slam.py
Les poses initiales viennent des estimations TP1/TP2, jamais d'un relevé terrain.
"""
from __future__ import annotations

import csv
import copy
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "resultats"
sys.path.insert(0, str(REPO / "tp1" / "LD06_Atelier"))
sys.path.insert(0, str(REPO / "tp2"))
from geometry import apply_pose, load_scan  # noqa: E402
from grid_map import GridMap  # noqa: E402
from vector_map import VectorMap  # noqa: E402
from localisation import ScanReference, coarse_icp, nearest_squared, objective, valid_scan, wrap  # noqa: E402


def inputs():
    tp1 = REPO / "tp1" / "TP1_4_scans"
    tp2 = REPO / "tp2" / "acquisitions"
    old = json.loads((tp1 / "poses.json").read_text(encoding="utf-8"))
    names = ["scan3", "scan4", "A_01", "A_02", "A_03", "B_01", "B_02", "B_03", "scan1", "scan2"]
    paths = {
        **{f"scan{i}": tp1 / "data" / f"scan{i}.csv" for i in range(1, 5)},
        **{f"A_0{i}": tp2 / "position_A_20261103_120212" / f"A_0{i}.csv" for i in range(1, 4)},
        **{f"B_0{i}": tp2 / "position_B_20261103_120333" / f"B_0{i}.csv" for i in range(1, 4)},
    }
    seeds = {f"scan{i}": old[f"scan{i}.csv"] for i in range(1, 5)}
    with (REPO / "tp2" / "resultats" / "poses_estimees_csv.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row["scan"] in paths:
                seeds[row["scan"]] = [float(row[k].replace(",", ".")) for k in ("x_estime_m", "y_estime_m", "angle_estime_deg")]
    return [(name, paths[name], valid_scan(load_scan(paths[name])), np.asarray(seeds[name], float)) for name in names]


def compact_cloud(points, limit=700, voxel=.07):
    """One representative per occupied voxel, then a bounded deterministic sample."""
    points = np.asarray(points, float)
    _, indices = np.unique(np.floor(points / voxel).astype(np.int32), axis=0, return_index=True)
    points = points[np.sort(indices)]
    if len(points) > limit:
        points = points[np.linspace(0, len(points) - 1, limit).astype(int)]
    return points


def make_grid(items, resolution=.08):
    """Allocate bounds from initial poses; no future impact is inserted yet."""
    projected = []
    for _, _, cloud, seed in items:
        projected.append(apply_pose(cloud, *seed))
        projected.append(seed[:2][None, :])
    points = np.vstack(projected)
    low = np.floor((points.min(axis=0) - 3) / resolution) * resolution
    high = np.ceil((points.max(axis=0) + 3) / resolution) * resolution
    return GridMap(low, high - low, resolution)


def quality(query, reference_points, pose):
    transformed = apply_pose(query, *pose)
    d = np.sqrt(nearest_squared(transformed, reference_points))
    return {
        "within_20cm": float(np.mean(d < .20)),
        "within_30cm": float(np.mean(d < .30)),
        "median_distance_m": float(np.median(d)),
    }


def draw_map(grid, pose_rows, path, title, segments=None, clouds=None):
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    pixels = np.where(grid.cells == -1, 0, np.where(grid.cells == 0, 1, 2))
    ax.imshow(pixels, origin="lower", extent=grid.extent, cmap=ListedColormap(["#ffffff", "#e8f1e3", "#664630"]), vmin=0, vmax=2, interpolation="nearest")
    if clouds:
        palette = plt.get_cmap("tab10")
        for k, (name, points) in enumerate(clouds):
            ax.scatter(points[:, 0], points[:, 1], s=1.2, color=palette(k % 10), alpha=.30, label=name)
    if segments:
        for item in segments:
            s = item["segment"]
            ax.plot(s[:, 0], s[:, 1], color="#1661a2", lw=1.15, alpha=.85)
    labeled = []
    for row in pose_rows:
        if row["status"] != "ajoute":
            continue
        x, y, angle = row["pose_estimee"]
        ax.plot(x, y, "o", ms=5, color="#c52424")
        if all(np.linalg.norm(np.array([x, y]) - previous) > .22 for previous in labeled):
            ax.annotate(row["scan"], (x, y), xytext=(4, 5), textcoords="offset points", fontsize=8)
            labeled.append(np.array([x, y]))
        ax.arrow(x, y, .35 * np.cos(np.deg2rad(angle)), .35 * np.sin(np.deg2rad(angle)), width=.012, color="#c52424", length_includes_head=True)
    ax.set(xlabel="X (m)", ylabel="Y (m)", title=title)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=.15)
    yy, xx = np.where(grid.cells == 100)
    if len(xx):
        low = grid.origin + np.array([xx.min(), yy.min()]) * grid.resolution - .7
        high = grid.origin + np.array([xx.max() + 1, yy.max() + 1]) * grid.resolution + .7
        ax.set_xlim(low[0], high[0])
        ax.set_ylim(low[1], high[1])
    fig.savefig(path, dpi=165)
    plt.close(fig)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    items = inputs()
    grid = make_grid(items)
    vector = VectorMap()
    rows, accepted, fused = [], [], []
    snapshots = []
    for index, (name, path, cloud, seed) in enumerate(items):
        t0 = time.perf_counter()
        if index == 0:
            pose = np.zeros(3)
            info = {"score": 0.0, "evaluations": 0, "iterations": 0}
            fit = {"within_20cm": None, "within_30cm": None, "median_distance_m": None}
            accepted_here = True
            reason = "origine de la carte"
        else:
            reference_points = compact_cloud(np.vstack(accepted))
            model = ScanReference(reference_points, resolution=.08)
            candidate, info = coarse_icp(cloud[::2], model, seed)
            # A prior estimate is retained when it fits the growing map better.
            seed_cost = objective(model, cloud[::2], seed)
            pose = candidate if info["score"] <= seed_cost else seed.copy()
            score = objective(model, cloud[::2], pose)
            info = {**info, "score": score, "initial_score": seed_cost}
            fit = quality(cloud, reference_points, pose)
            shift = float(np.linalg.norm(pose[:2] - seed[:2]))
            turn = abs(wrap(pose[2] - seed[2]))
            # An unrelated or severely mismatched scan must not corrupt the map.
            accepted_here = fit["within_30cm"] >= .32 and score <= .11 and shift <= 1.5 and turn <= 35
            reason = "recouvrement et ecart a l'initialisation acceptes" if accepted_here else "recouvrement insuffisant ou pose trop eloignee de l'initialisation"
        row = {
            "scan": name, "source": str(path.relative_to(REPO)).replace("\\", "/"),
            "points": len(cloud), "pose_initiale": seed.tolist(), "pose_estimee": pose.tolist(),
            "status": "ajoute" if accepted_here else "ecarte", "reason": reason,
            "height_m": 1.90, "height_source": "declaration utilisateur ou protocole A/B, non mesuree par le LiDAR",
            "quality": fit, "matching": info, "seconds": time.perf_counter() - t0,
        }
        if accepted_here:
            grid.update(cloud, pose)
            vector.update(cloud, pose, clear_crossed=False)
            world = apply_pose(cloud, *pose)
            accepted.append(world)
            fused.append((name, cloud, world))
            draw_map(grid, rows + [row], OUT / f"etape_{len(fused):02d}.png", f"Etape {len(fused)} : ajout de {name}")
            snapshots.append(grid.cells.copy())
        rows.append(row)
        print(f"{name}: {row['status']}, pose={np.round(pose, 3)}, score={info['score']:.4f}, recouvrement={fit['within_30cm']}", flush=True)
    grid.export(OUT / "grid_map")
    vector.export(OUT / "carte_vectorielle.csv")
    # A second, explicitly provisional map shows what the rejected scan would add.
    # It does not replace the quality-controlled main result.
    rejected = [row for row in rows if row["status"] == "ecarte"]
    if rejected:
        exploratory_grid = GridMap(grid.origin, np.array(grid.cells.shape[::-1]) * grid.resolution, grid.resolution)
        exploratory_grid.cells = grid.cells.copy()
        exploratory_grid.scan_count = grid.scan_count
        exploratory_vector = copy.deepcopy(vector)
        exploratory_clouds = [(name, world) for name, _, world in fused]
        for row in rejected:
            cloud = next(item[2] for item in items if item[0] == row["scan"])
            pose = row["pose_estimee"]
            exploratory_grid.update(cloud, pose)
            exploratory_vector.update(cloud, pose, clear_crossed=False)
            exploratory_clouds.append((row["scan"], apply_pose(cloud, *pose)))
        exploratory_grid.export(OUT / "grid_map_exploratoire")
        exploratory_vector.export(OUT / "carte_vectorielle_exploratoire.csv")
        exploratory_rows = [{**row, "status": "ajoute"} for row in rows]
        draw_map(exploratory_grid, exploratory_rows, OUT / "carte_exploratoire.png",
                 "Carte exploratoire : scans écartés ajoutés sans garantie", segments=exploratory_vector.features,
                 clouds=exploratory_clouds)
    with (OUT / "points_fusionnes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["scan", "x_local_m", "y_local_m", "x_carte_m", "y_carte_m"])
        for name, cloud, world in fused:
            writer.writerows((name, *local, *global_point) for local, global_point in zip(cloud, world))
    with (OUT / "poses_et_qualite.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["scan", "statut", "x_m", "y_m", "angle_deg", "recouvrement_20cm", "recouvrement_30cm", "score", "temps_s"])
        for row in rows:
            writer.writerow([row["scan"], row["status"], *row["pose_estimee"], row["quality"]["within_20cm"], row["quality"]["within_30cm"], row["matching"]["score"], row["seconds"]])
    (OUT / "diagnostic.json").write_text(json.dumps({"method": "scan_coarse_icp sur nuage global croissant", "initial_pose_source": "estimations TP1/TP2", "accepted": len(fused), "total": len(items), "grid_resolution_m": grid.resolution, "grid_extent_m": grid.extent, "vector_segments": len(vector.features), "exploratory_map": bool(rejected), "scans": rows, "ground_truth_available": False, "excluded_other_scans": "N1,N2,N3,N5,N6: hauteur estimee 1,00-1,20 m; N4: sol"}, indent=2, ensure_ascii=False), encoding="utf-8")
    draw_map(grid, rows, OUT / "carte_finale.png", f"TP3 : carte progressive ({len(fused)}/{len(items)} scans ajoutes)", segments=vector.features, clouds=[(n, w) for n, _, w in fused])
    fig, axes = plt.subplots(2, 5, figsize=(18, 8), constrained_layout=True)
    occupied_y, occupied_x = np.where(grid.cells == 100)
    crop_low = grid.origin + np.array([occupied_x.min(), occupied_y.min()]) * grid.resolution - .7
    crop_high = grid.origin + np.array([occupied_x.max() + 1, occupied_y.max() + 1]) * grid.resolution + .7
    for ax, snapshot, row in zip(axes.flat, snapshots, [r for r in rows if r["status"] == "ajoute"]):
        pixels = np.where(snapshot == -1, 0, np.where(snapshot == 0, 1, 2))
        ax.imshow(pixels, origin="lower", extent=grid.extent, cmap=ListedColormap(["white", "#e8f1e3", "#664630"]), vmin=0, vmax=2)
        ax.set_title(row["scan"])
        ax.set_aspect("equal")
        ax.set_xlim(crop_low[0], crop_high[0])
        ax.set_ylim(crop_low[1], crop_high[1])
    for ax in axes.flat[len(snapshots):]:
        ax.axis("off")
    fig.suptitle("Construction progressive de la grid map")
    fig.savefig(OUT / "progression.png", dpi=150)
    plt.close(fig)
    return rows


if __name__ == "__main__":
    run()
