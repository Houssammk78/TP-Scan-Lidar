"""Aligne les sous-cartes mobiles sur la carte TP3 antérieure, à titre exploratoire.

Ce script ne crée aucune vérité terrain : les résultats sont des hypothèses
géométriques indépendantes, et la carte antérieure sert d'ancrage explicite.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "tp1" / "LD06_Atelier"))
sys.path.insert(0, str(REPO / "tp2"))
sys.path.insert(0, str(ROOT))
from geometry import apply_pose  # noqa: E402
from localisation import ScanReference, objective_batch  # noqa: E402
from mobile_slam import local_icp  # noqa: E402


def occupied_points(npz):
    with np.load(npz, allow_pickle=False) as data:
        cells = data["cells"]
        origin = data["origin"]
        resolution = float(data["resolution"])
    y, x = np.where(cells == 100)
    points = origin + (np.column_stack([x, y]) + .5) * resolution
    return points, cells, origin, resolution


def downsample(points, limit=250):
    return points[np.linspace(0, len(points) - 1, min(limit, len(points))).astype(int)]


def estimate_on_prior(query, reference, field):
    small = downsample(query)
    center = np.median(reference, axis=0)
    offsets = np.arange(-3.6, 3.61, .9)
    guesses = []
    for angle in np.arange(-180, 180, 15):
        rotated = apply_pose(small, 0, 0, angle)
        base = center - np.median(rotated, axis=0)
        for dx in offsets:
            for dy in offsets:
                guesses.append([base[0] + dx, base[1] + dy, float(angle)])
    guesses = np.asarray(guesses)
    costs = objective_batch(field, small, guesses, batch_size=24)
    candidates = []
    for index in np.argsort(costs):
        candidate = guesses[index]
        if all(np.linalg.norm(candidate[:2] - other[:2]) > .7 or
               abs((candidate[2] - other[2] + 180) % 360 - 180) > 15 for other in candidates):
            candidates.append(candidate)
            if len(candidates) >= 8:
                break
    trials = [local_icp(small, reference, initial) for initial in candidates]
    pose, quality = min(trials, key=lambda item: item[1]["score_m2"])
    return pose, quality


def run(out=ROOT / "resultats_rejeu"):
    out = Path(out)
    summary = json.loads((out / "bilan_rejeu.json").read_text(encoding="utf-8"))
    prior_file = REPO / "tp3" / "resultats" / "grid_map_exploratoire.npz"
    reference, prior_cells, prior_origin, prior_resolution = occupied_points(prior_file)
    field = ScanReference(reference, resolution=.12)
    rows, clouds = [], []
    for item in summary["submaps"]:
        source = out / item["folder"] / "grid_map_mobile.npz"
        points, _, _, _ = occupied_points(source)
        pose, quality = estimate_on_prior(points, reference, field)
        row = dict(submap=item["folder"], scans_accepted=item["accepted"],
                   x_m=float(pose[0]), y_m=float(pose[1]), angle_deg=float(pose[2]),
                   **quality)
        # Exploratory label only. It does not prove the recovered pose.
        row["visual_status"] = "plausible" if quality["within_30cm"] >= .35 and quality["score_m2"] <= .12 else "incertain"
        rows.append(row)
        clouds.append((item["folder"], apply_pose(points, *pose), row))
        print(item["folder"], row["visual_status"], np.round(pose, 2),
              round(quality["within_30cm"], 2), round(quality["score_m2"], 3), flush=True)
    with (out / "raccords_exploratoires.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    with (out / "points_regroupes_exploratoires.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["sous_carte", "statut_visuel", "x_dans_repere_tp3_m", "y_dans_repere_tp3_m"])
        for name, points, row in clouds:
            writer.writerows((name, row["visual_status"], float(x), float(y)) for x, y in points)
    (out / "raccords_exploratoires.json").write_text(json.dumps({
        "reference": str(prior_file.relative_to(REPO)).replace("\\", "/"),
        "method": "recherche grossiere de poses puis ICP sur cellules occupees",
        "ground_truth_available": False,
        "warning": "Raccords approximatifs, non valides par mesure physique. Ne pas utiliser pour navigation.",
        "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(11, 10), constrained_layout=True)
    pixels = np.where(prior_cells == -1, 0, np.where(prior_cells == 0, 1, 2))
    extent = [prior_origin[0], prior_origin[0] + prior_cells.shape[1] * prior_resolution,
              prior_origin[1], prior_origin[1] + prior_cells.shape[0] * prior_resolution]
    ax.imshow(pixels, origin="lower", extent=extent,
              cmap=ListedColormap(["#ffffff", "#e4efe0", "#8a6b58"]), vmin=0, vmax=2, alpha=.7)
    palette = plt.get_cmap("tab20")
    for index, (name, points, row) in enumerate(clouds):
        plausible = row["visual_status"] == "plausible"
        ax.scatter(points[:, 0], points[:, 1], s=5 if plausible else 3,
                   color=palette(index), alpha=.55 if plausible else .18,
                   label=f"{index + 1:02d} {name} {'✓' if plausible else '?'}")
        if plausible:
            ax.annotate(str(index + 1), (row["x_m"], row["y_m"]), fontsize=7,
                        color=palette(index), weight="bold")
    ax.set(xlabel="X du TP3 antérieur (m)", ylabel="Y du TP3 antérieur (m)",
           title="Résultat final du TP3 — regroupement estimé")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(extent[0] - .4, extent[1] + .4)
    ax.set_ylim(extent[2] - .4, extent[3] + .4)
    ax.grid(alpha=.16)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, .5), fontsize=7, title="Sous-carte / statut")
    final_image = REPO / "tp3" / "resultats" / "resultat_final.png"
    final_image.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(final_image, dpi=175)
    plt.close(fig)
    return rows


if __name__ == "__main__":
    run()
