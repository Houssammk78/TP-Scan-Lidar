"""Analyse exploratoire des six acquisitions du 3 novembre à 15 h.

Le scan N4 a été pris au sol : il reste dans les diagnostics mais n'entre
pas dans les comparaisons de méthodes à hauteur commune.
"""
import csv
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from evaluer import csv_save
from localisation import METHODS, ScanReference, coarse_icp, nearest_squared, valid_scan
from geometry import apply_pose, load_scan

IDS = ["150228", "150436", "150607", "150714", "150922", "151020"]
FLOOR_SCAN = "N4"
INITIALS = [(0, 0, 0), (.5, -.25, 0), (-.5, .3, 0),
            (0, 0, 90), (0, 0, 180), (0, 0, -90)]
OUT = ROOT / "resultats_nouveaux_scans"


def input_file(identifier):
    stamp = "20261103_" + identifier
    return ROOT / "acquisitions" / ("scan_" + stamp) / ("scan_" + stamp + ".csv")


def overlap(reference, query, pose):
    aligned = apply_pose(query, *pose)
    query_to_reference = np.sqrt(nearest_squared(aligned, reference))
    reference_to_query = np.sqrt(nearest_squared(reference, aligned))
    return dict(
        query_20cm=float(np.mean(query_to_reference < .2)),
        reference_20cm=float(np.mean(reference_to_query < .2)),
        query_50cm=float(np.mean(query_to_reference < .5)),
        reference_50cm=float(np.mean(reference_to_query < .5)),
    )


def diagnostic_pairs(clouds):
    rows = []
    for i in range(1, 6):
        reference = clouds[f"N{i}"]
        model = ScanReference(reference)
        for j in range(i + 1, 7):
            query = clouds[f"N{j}"]
            start = time.perf_counter()
            candidates = [coarse_icp(query, model, [0, 0, heading])
                          for heading in (0, 180)]
            pose, info = min(candidates, key=lambda item: item[1]["score"])
            coverage = overlap(reference, query, pose)
            same_height = i != 4 and j != 4
            eligible = (same_height and
                        min(coverage["query_20cm"], coverage["reference_20cm"]) >= .4 and
                        min(coverage["query_50cm"], coverage["reference_50cm"]) >= .7)
            rows.append(dict(
                reference=f"N{i}", scan=f"N{j}", same_height=same_height,
                selected_for_comparison=eligible,
                estimated_x_m=float(pose[0]), estimated_y_m=float(pose[1]),
                estimated_angle_deg=float(pose[2]),
                residual_rms_capped_m=float(np.sqrt(info["score"])),
                **coverage, diagnostic_seconds=time.perf_counter() - start,
            ))
    return rows


def compare_methods(clouds, selected):
    rows = []
    illustrated = {}
    for pair in selected:
        reference_name, scan_name = pair["reference"], pair["scan"]
        reference, query = clouds[reference_name], clouds[scan_name]
        models = {}
        build_times = {}
        for method, (cls, _) in METHODS.items():
            start = time.perf_counter()
            models[method] = cls(reference)
            build_times[method] = time.perf_counter() - start
        for trial, initial in enumerate(INITIALS):
            for method, (_, solver) in METHODS.items():
                start = time.perf_counter()
                pose, info = solver(query, models[method], initial)
                seconds = time.perf_counter() - start
                coverage = overlap(reference, query, pose)
                rows.append(dict(
                    reference=reference_name, scan=scan_name, trial=trial,
                    method=method, initial_x_m=initial[0],
                    initial_y_m=initial[1], initial_angle_deg=initial[2],
                    estimated_x_m=float(pose[0]),
                    estimated_y_m=float(pose[1]),
                    estimated_angle_deg=float(pose[2]),
                    residual_rms_native_m=float(np.sqrt(info["score"])),
                    **coverage,
                    solve_seconds=seconds,
                    reference_build_seconds=build_times[method],
                    position_error_m=None, angle_error_deg=None, success=None,
                ))
                if trial == 4:
                    illustrated[(reference_name, scan_name, method)] = pose
        print(reference_name, scan_name, "comparés", flush=True)
    return rows, illustrated


def figures(clouds, selected, illustrated):
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for index, (label, points) in enumerate(clouds.items()):
        ax = axes.flat[index]
        ax.scatter(points[:, 0], points[:, 1], s=6, color="#1976d2")
        ax.plot(0, 0, "+", color="#c62828", markersize=11)
        suffix = " (au sol)" if label == FLOOR_SCAN else ""
        ax.set(title=label + suffix, xlabel="X local (m)", ylabel="Y local (m)")
        ax.set_aspect("equal")
        ax.grid(alpha=.2)
    fig.suptitle("Six acquisitions LD06 - repères locaux distincts")
    fig.tight_layout()
    fig.savefig(OUT / "six_scans_bruts.png", dpi=150)
    plt.close(fig)
    if not selected:
        return
    pair = selected[0]
    name, scan = pair["reference"], pair["scan"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, method in zip(axes, METHODS):
        transformed = apply_pose(clouds[scan], *illustrated[(name, scan, method)])
        ax.scatter(*clouds[name].T, s=7, color="#9e9e9e", label=name + " référence")
        ax.scatter(*transformed.T, s=7, color="#1976d2", label=scan + " estimé")
        ax.set(title=method, xlabel="X (m)", ylabel="Y (m)")
        ax.set_aspect("equal")
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle("Même paire et même départ (0, 0, 180°) - pose réelle inconnue")
    fig.tight_layout()
    fig.savefig(OUT / "comparaison_paire_selectionnee.png", dpi=150)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    paths = {f"N{i}": input_file(identifier) for i, identifier in enumerate(IDS, 1)}
    clouds = {label: valid_scan(load_scan(path))[::3] for label, path in paths.items()}
    quality = []
    for label, path in paths.items():
        meta = json.loads((path.parent / "acquisition.json").read_text(encoding="utf-8"))
        quality.append(dict(scan=label, csv_path=str(path.relative_to(ROOT)),
                            points_acquired=meta["point_count"],
                            points_compared=len(clouds[label]),
                            angular_coverage_deg=meta["angular_coverage_deg"],
                            height_group="au sol" if label == FLOOR_SCAN else "environ 1,00 à 1,20 m (estimation)"))
    csv_save(OUT / "qualite_scans.csv", quality)
    pairs = diagnostic_pairs(clouds)
    csv_save(OUT / "recouvrement_paires.csv", pairs)
    selected = [row for row in pairs if row["selected_for_comparison"]]
    comparisons, illustrated = compare_methods(clouds, selected)
    if comparisons:
        csv_save(OUT / "comparaison_methodes.csv", comparisons)
        # Common pairs and starts for all three solvers are a reproducible gate.
        groups = {}
        for row in comparisons:
            groups.setdefault((row["reference"], row["scan"], row["trial"]), []).append(row)
        assert all(len(group) == len(METHODS) and
                   len({(r["initial_x_m"], r["initial_y_m"], r["initial_angle_deg"])
                        for r in group}) == 1 for group in groups.values())
    figures(clouds, selected, illustrated)
    protocol = dict(
        reference_selection="Paires diagnostiquées avec la méthode entre scans depuis 0° et 180°. "
                            "Sélection si mêmes hauteurs annoncées et au moins 40% des points "
                            "appariés dans chaque sens à 20 cm, 70% à 50 cm.",
        note_selection="La sélection fondée sur le scan matching peut favoriser cette méthode. "
                       "Le recouvrement ne prouve ni la proximité physique ni la pose exacte.",
        selected_pairs=[[row["reference"], row["scan"]] for row in selected],
        initial_poses=INITIALS,
        scan_4="Pris au sol selon l'utilisateur ; exclu des comparaisons à hauteur commune.",
        common_height_estimated_range_m=[1.0, 1.2],
        height_source="Estimation de l'utilisateur, non mesurée au centimètre.",
        ground_truth_available=False,
        physical_position_uncertainty_m=None,
        physical_angle_uncertainty_deg=None,
        real_position_and_angle_errors="Non calculables sans mesure indépendante des poses.",
        real_success_rate="Non calculable sans mesure indépendante des poses.",
        counts=dict(scans=len(clouds),diagnostic_pairs=len(pairs),
                    comparable_pairs=len(selected),method_trials=len(comparisons)),
    )
    (OUT / "protocole_nouveaux_scans.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(protocol["counts"]), flush=True)
    print("Paires retenues:", protocol["selected_pairs"], flush=True)


if __name__ == "__main__":
    main()
