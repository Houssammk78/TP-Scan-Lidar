"""Figures SLAM calculées depuis les CSV et poses produits par tp3/slam.py."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "resultats"
sys.path.insert(0, str(REPO / "tp1" / "LD06_Atelier"))
sys.path.insert(0, str(REPO / "tp2"))
from geometry import apply_pose, load_scan  # noqa: E402
from localisation import valid_scan  # noqa: E402


def load_results():
    diagnostic = json.loads((OUT / "diagnostic.json").read_text(encoding="utf-8"))
    clouds = {}
    with (OUT / "points_fusionnes.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            clouds.setdefault(row["scan"], []).append((float(row["x_carte_m"]), float(row["y_carte_m"])))
    return diagnostic, {name: np.asarray(points) for name, points in clouds.items()}


def progression(diagnostic, clouds):
    accepted = [row["scan"] for row in diagnostic["scans"] if row["status"] == "ajoute"]
    stages = sorted(set([1, min(3, len(accepted)), min(6, len(accepted)), len(accepted)]))
    fig, axes = plt.subplots(2, 2, figsize=(12, 12), constrained_layout=True)
    all_points = np.vstack([clouds[name] for name in accepted])
    low = all_points.min(axis=0) - .6
    high = all_points.max(axis=0) + .6
    palette = plt.get_cmap("tab10")
    for ax, count in zip(axes.flat, stages):
        for index, name in enumerate(accepted[:count]):
            p = clouds[name]
            ax.scatter(p[:, 0], p[:, 1], s=2.4, alpha=.60, color=palette(index % 10), label=name)
        ax.set_title(f"Après {count} scan{'s' if count > 1 else ''} accepté{'s' if count > 1 else ''}")
        ax.set(xlim=(low[0], high[0]), ylim=(low[1], high[1]), xlabel="X (m)", ylabel="Y (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.18)
        ax.legend(loc="upper right", fontsize=7, markerscale=2)
    for ax in axes.flat[len(stages):]:
        ax.axis("off")
    fig.suptitle("SLAM : construction de la carte scan après scan", fontsize=16)
    fig.savefig(OUT / "slam_progression_nuages.png", dpi=165)
    plt.close(fig)


def recalage(diagnostic, clouds):
    # scan3 is the first accepted scan after scan1 in the chronological replay.
    row = next(item for item in diagnostic["scans"] if item["scan"] == "scan3")
    reference = clouds["scan1"]
    raw = valid_scan(load_scan(REPO / row["source"]))
    aligned = apply_pose(raw, *row["pose_estimee"])
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
    for ax, query, title in zip(axes, (raw, aligned), ("Avant localisation", "Après localisation")):
        ax.scatter(reference[:, 0], reference[:, 1], s=7, color="#1665a6", alpha=.65, label="Carte existante : scan 1")
        ax.scatter(query[:, 0], query[:, 1], s=7, color="#e78119", alpha=.65, label="Nouveau : scan 3")
        ax.set(title=title, xlabel="X (m)", ylabel="Y (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.18)
        ax.legend(loc="upper right", fontsize=9)
    sample = aligned[::8]
    distances = ((sample[:, None, :] - reference[None, :, :]) ** 2).sum(axis=2)
    nearest = distances.argmin(axis=1)
    for point, idx, square in zip(sample, nearest, distances[np.arange(len(sample)), nearest]):
        if square < .20 ** 2:
            axes[1].plot([point[0], reference[idx, 0]], [point[1], reference[idx, 1]],
                         color="#1a9b56", lw=.6, alpha=.6)
    fig.suptitle("SLAM : un scan localisé avant son insertion dans la carte", fontsize=15)
    fig.savefig(OUT / "slam_recalage_scan3.png", dpi=170)
    plt.close(fig)


def main():
    diagnostic, clouds = load_results()
    if "scan1" not in clouds or "scan3" not in clouds:
        raise ValueError("Les résultats TP3 chronologiques requis sont absents")
    progression(diagnostic, clouds)
    recalage(diagnostic, clouds)
    print("Figures SLAM générées dans", OUT)


if __name__ == "__main__":
    main()
