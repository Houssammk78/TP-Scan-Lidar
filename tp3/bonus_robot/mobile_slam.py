"""Rejeu des acquisitions du robot et boucle SLAM stop-scan-go en direct.

Les octets 0..5 du paquet /scan sont des valeurs réglables via /pose : ils ne
sont pas une odométrie et ne servent jamais à estimer la trajectoire.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tp1" / "LD06_Atelier"))
sys.path.insert(0, str(REPO / "tp2"))
sys.path.insert(0, str(REPO / "tp3"))
from geometry import apply_pose  # noqa: E402
from grid_map import GridMap  # noqa: E402
from localisation import nearest_squared, valid_scan, wrap  # noqa: E402
from slam import compact_cloud, expand_grid, make_grid  # noqa: E402


@dataclass
class Scan:
    name: str
    stamp: str
    points: np.ndarray
    raw_count: int
    source: str
    embedded_pose: tuple[float, float, float] | None = None


def points_from_rows(rows):
    """Use the x/y convention already written by the acquisition tool."""
    return np.array([[float(r["x_lib_mm"]) / 1000, float(r["y_lib_mm"]) / 1000] for r in rows], float)


def load_combined(path):
    groups = OrderedDict()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scan_id", "horodatage_pc", "point_index", "x_lib_mm", "y_lib_mm"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Colonnes manquantes dans {path}")
        for row in reader:
            key = (row["scan_id"], row["horodatage_pc"])
            groups.setdefault(key, []).append(row)
    scans = []
    for (number, stamp), rows in groups.items():
        indices = [int(row["point_index"]) for row in rows]
        if indices != list(range(len(rows))):
            raise ValueError(f"Scan {number} incomplet ou points dans le désordre")
        pose = tuple(float(rows[0][key]) for key in ("pose_x", "pose_y", "pose_angle_deg"))
        scans.append(Scan(f"R{int(number):03d}", stamp, points_from_rows(rows), len(rows), str(path), pose))
    return scans


def load_individual(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if [int(row["point_index"]) for row in rows] != list(range(len(rows))):
        raise ValueError(f"Points incomplets dans {path}")
    return Scan(Path(path).stem, Path(path).stem, points_from_rows(rows), len(rows), str(path))


def load_acquisition(combined, singles=()):
    """One cumulative export plus later single scans; deduplicate exact scan content."""
    scans = load_combined(combined)
    scans.extend(load_individual(path) for path in sorted(singles))
    seen, unique = set(), []
    for scan in scans:
        signature = hashlib.sha256(np.round(scan.points * 1000).astype("<i4").tobytes()).hexdigest()
        if signature not in seen:
            seen.add(signature)
            unique.append(scan)
    return unique


def decode_packet(data, name="live", stamp=""):
    if len(data) < 8:
        raise ValueError("Paquet LiDAR trop court")
    pose_x, pose_y, heading, count = struct.unpack_from("<hhHH", data)
    if not 1 <= count <= 460 or len(data) != 8 + 5 * count:
        raise ValueError("Longueur de paquet LiDAR invalide")
    points = np.empty((count, 2), float)
    for index in range(count):
        angle, distance, _ = struct.unpack_from("<HHB", data, 8 + 5 * index)
        radians = math.radians(angle / 100)
        points[index] = [distance * math.cos(radians) / 1000,
                         -distance * math.sin(radians) / 1000]
    return Scan(name, stamp, points, count, "http:/scan", (pose_x, pose_y, heading / 100))


def rigid_fit(source, target):
    a, b = source.mean(axis=0), target.mean(axis=0)
    u, _, vt = np.linalg.svd((source - a).T @ (target - b))
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1] *= -1
        rotation = vt.T @ u.T
    translation = b - rotation @ a
    return rotation, translation


def local_icp(points, reference, initial, max_iter=24):
    """Trimmed point-to-point ICP around the previous accepted pose."""
    pose = np.asarray(initial, float).copy()
    target = compact_cloud(reference, limit=1200, voxel=.06)
    query = points[::2]
    for _ in range(max_iter):
        transformed = apply_pose(query, *pose)
        squared = (transformed * transformed).sum(1)[:, None] + (target * target).sum(1)[None, :] - 2 * transformed @ target.T
        indices = squared.argmin(axis=1)
        distances = np.sqrt(np.maximum(squared[np.arange(len(query)), indices], 0))
        threshold = min(.65, max(.12, float(np.quantile(distances, .65))))
        keep = distances <= threshold
        if keep.sum() < 12:
            break
        rotation, translation = rigid_fit(transformed[keep], target[indices[keep]])
        angle = math.degrees(math.atan2(rotation[1, 0], rotation[0, 0]))
        pose[:2] = rotation @ pose[:2] + translation
        pose[2] = wrap(pose[2] + angle)
        if np.linalg.norm(translation) < .0005 and abs(angle) < .01:
            break
    transformed = apply_pose(points, *pose)
    d = np.sqrt(nearest_squared(transformed, target))
    quality = dict(median_m=float(np.median(d)), within_30cm=float(np.mean(d < .30)),
                   score_m2=float(np.mean(np.minimum(d, .6) ** 2)))
    return pose, quality


class IncrementalSlam:
    def __init__(self, resolution=.10):
        self.resolution = resolution
        self.grid = None
        self.reference = []
        self.rows = []
        self.last_pose = np.zeros(3)

    def add(self, scan):
        cloud = valid_scan(scan.points)
        if self.grid is None:
            pose = np.zeros(3)
            quality = dict(median_m=0., within_30cm=1., score_m2=0.)
            accepted = True
            self.grid = make_grid(cloud, self.resolution)
        else:
            # Nearby robot poses are the only justified prior for a timed sequence.
            reference = compact_cloud(np.vstack(self.reference[-5:]), limit=1200, voxel=.06)
            candidates = []
            for delta in (0, -12, 12):
                guess = self.last_pose.copy()
                guess[2] = wrap(guess[2] + delta)
                candidates.append(local_icp(cloud, reference, guess))
            pose, quality = min(candidates, key=lambda item: item[1]["score_m2"])
            accepted = quality["within_30cm"] >= .40 and quality["score_m2"] <= .09
        row = dict(scan=scan.name, stamp=scan.stamp, source=scan.source,
                   raw_points=scan.raw_count, valid_points=len(cloud),
                   status="ajoute" if accepted else "ecarte",
                   x_m=float(pose[0]), y_m=float(pose[1]), angle_deg=float(pose[2]),
                   **quality)
        self.rows.append(row)
        if accepted:
            expand_grid(self.grid, cloud, pose)
            self.grid.update(cloud, pose)
            self.reference.append(apply_pose(cloud, *pose))
            self.last_pose = pose
        return row

    def save(self, out):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        if self.grid is None:
            return
        self.grid.export(out / "grid_map_mobile")
        with (out / "trajectoire.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.rows[0]), delimiter=";")
            writer.writeheader()
            writer.writerows(self.rows)
        accepted = [row for row in self.rows if row["status"] == "ajoute"]
        summary = dict(scans_total=len(self.rows), scans_accepted=len(accepted),
                       scans_rejected=len(self.rows) - len(accepted),
                       occupied_cells=int(np.sum(self.grid.cells == 100)),
                       free_cells=int(np.sum(self.grid.cells == 0)),
                       ground_truth_available=False,
                       embedded_pose_used=False,
                       map_extent_m=self.grid.extent)
        (out / "bilan.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        pixels = np.where(self.grid.cells == -1, 0, np.where(self.grid.cells == 0, 1, 2))
        fig, ax = plt.subplots(figsize=(11, 9), constrained_layout=True)
        ax.imshow(pixels, origin="lower", extent=self.grid.extent,
                  cmap=ListedColormap(["#f5f6f8", "#d8eed6", "#68482f"]), vmin=0, vmax=2)
        for world in self.reference:
            ax.scatter(world[::3, 0], world[::3, 1], s=1.2, c="#1769aa", alpha=.32)
        xy = np.array([[row["x_m"], row["y_m"]] for row in accepted])
        ax.plot(xy[:, 0], xy[:, 1], "-o", color="#cc2828", lw=1.4, ms=2.2, label="Trajectoire estimée")
        ax.scatter(xy[0, 0], xy[0, 1], c="#2334b4", s=70, marker="*", label="Départ")
        ax.set(xlabel="X (m)", ylabel="Y (m)",
               title=f"SLAM mobile : {len(accepted)}/{len(self.rows)} scans intégrés")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.15)
        ax.legend()
        fig.savefig(out / "slam_mobile.png", dpi=165)
        plt.close(fig)


class Robot:
    def __init__(self, base="http://192.168.4.1", timeout=2):
        self.base, self.timeout = base.rstrip("/"), timeout

    def get(self, path):
        with urlopen(Request(self.base + path, headers={"Cache-Control": "no-cache"}), timeout=self.timeout) as response:
            return response.read()

    def stop(self):
        self.get("/stop")

    def fresh_scan(self, name, max_age_ms=350, wait_s=3):
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            status = json.loads(self.get("/lidar_status"))
            if status.get("enabled") and status.get("points", 0) >= 100 and 0 <= status.get("age_ms", -1) <= max_age_ms:
                return decode_packet(self.get("/scan"), name, time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            time.sleep(.10)
        raise TimeoutError("Aucun scan LiDAR frais : robot arrêté")


def front_clearance(points, sector_deg=25):
    """Firmware: angle 0 = +X local. Ignore invalid and isolated close returns."""
    r = np.linalg.norm(points, axis=1)
    a = np.abs(np.degrees(np.arctan2(-points[:, 1], points[:, 0])))
    keep = np.isfinite(r) & (r >= .15) & (r <= 12) & (a <= sector_deg)
    if keep.sum() < 8:
        raise ValueError("Secteur frontal mal observé")
    return float(np.quantile(r[keep], .10))


def live(robot, out, steps=20, min_clearance=.9):
    """Automatic forward pulses only; blocked/lost scan/match -> STOP."""
    engine = IncrementalSlam()
    out = Path(out)
    try:
        robot.stop()
        for index in range(steps + 1):
            scan = robot.fresh_scan(f"L{index:03d}")
            raw_dir = out / "scans_bruts"
            raw_dir.mkdir(parents=True, exist_ok=True)
            with (raw_dir / f"{scan.name}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["point_index", "x_lib_mm", "y_lib_mm"])
                writer.writerows((i, round(p[0] * 1000), round(p[1] * 1000)) for i, p in enumerate(scan.points))
            clearance = front_clearance(scan.points)
            row = engine.add(scan)
            engine.save(out)
            print(f"{row['scan']}: {row['status']}, avant={clearance:.2f} m, pose=({row['x_m']:.2f},{row['y_m']:.2f},{row['angle_deg']:.1f}°)", flush=True)
            if index == steps or row["status"] != "ajoute" or clearance < min_clearance:
                break
            robot.get("/forward")
            # The firmware's measured pulse schedule lasts about 650 ms.
            time.sleep(.80)
            robot.stop()
            time.sleep(.25)
    finally:
        try:
            robot.stop()
        except Exception as exc:
            print(f"ATTENTION : arrêt distant non confirmé : {exc}", file=sys.stderr)
        engine.save(out)
    return engine


def replay_segmented(scans, out, missed_limit=3):
    """Never place a disconnected acquisition into an invented global frame."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    segments = []
    engine = IncrementalSlam()
    missed = 0
    for index, scan in enumerate(scans, 1):
        row = engine.add(scan)
        if row["status"] == "ajoute":
            missed = 0
        else:
            missed += 1
        if missed >= missed_limit:
            # Move this failed transition to the new local frame; do not count
            # the same acquisition twice in the replay summary.
            engine.rows.pop()
            folder = out / f"sous_carte_{len(segments) + 1:02d}"
            engine.save(folder)
            segments.append(dict(folder=folder.name, first=engine.rows[0]["scan"],
                                 last=engine.rows[-1]["scan"], scans=len(engine.rows),
                                 accepted=sum(r["status"] == "ajoute" for r in engine.rows)))
            engine = IncrementalSlam()
            engine.add(scan)
            missed = 0
        if index % 10 == 0 or index == len(scans):
            print(f"{index}/{len(scans)} : sous-cartes={len(segments)+1}, scan={row['status']}", flush=True)
    folder = out / f"sous_carte_{len(segments) + 1:02d}"
    engine.save(folder)
    segments.append(dict(folder=folder.name, first=engine.rows[0]["scan"],
                         last=engine.rows[-1]["scan"], scans=len(engine.rows),
                         accepted=sum(r["status"] == "ajoute" for r in engine.rows)))
    summary = dict(source_scans=len(scans), submaps=segments,
                   note="Repères locaux indépendants. Aucune pose relative fiable entre sous-cartes.",
                   ground_truth_available=False)
    (out / "bilan_rejeu.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = 3
    rows = math.ceil(len(segments) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(15, 4.2 * rows), constrained_layout=True)
    for ax, segment in zip(np.asarray(axes).flat, segments):
        npz = out / segment["folder"] / "grid_map_mobile.npz"
        with np.load(npz, allow_pickle=False) as data:
            cells, origin, resolution = data["cells"], data["origin"], float(data["resolution"])
        extent = [origin[0], origin[0] + cells.shape[1] * resolution,
                  origin[1], origin[1] + cells.shape[0] * resolution]
        pixels = np.where(cells == -1, 0, np.where(cells == 0, 1, 2))
        ax.imshow(pixels, origin="lower", extent=extent,
                  cmap=ListedColormap(["#f5f6f8", "#d8eed6", "#68482f"]), vmin=0, vmax=2)
        ax.set_title(f"{segment['folder']} : {segment['accepted']}/{segment['scans']} scans")
        ax.set_aspect("equal", adjustable="box")
        ax.set(xlabel="X local (m)", ylabel="Y local (m)")
    for ax in list(np.asarray(axes).flat)[len(segments):]:
        ax.axis("off")
    fig.suptitle("Rejeu robot : sous-cartes séparées après perte de localisation", fontsize=16)
    fig.savefig(out / "vue_sous_cartes.png", dpi=140)
    plt.close(fig)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", type=Path, help="Export cumulatif CSV du navigateur")
    parser.add_argument("--single", type=Path, nargs="*", default=[], help="Scans individuels ultérieurs")
    parser.add_argument("--output", type=Path, default=HERE / "resultats_mobile")
    parser.add_argument("--drive", action="store_true", help="Activer les impulsions motrices sur le vrai robot")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--min-clearance", type=float, default=.9)
    parser.add_argument("--base", default="http://192.168.4.1")
    args = parser.parse_args()
    if args.drive:
        if args.combined or args.single:
            parser.error("--drive ne s'utilise pas avec des CSV")
        if not 1 <= args.steps <= 100 or not .6 <= args.min_clearance <= 3:
            parser.error("steps entre 1 et 100 ; dégagement entre 0,6 et 3 m")
        live(Robot(args.base), args.output, args.steps, args.min_clearance)
    else:
        if not args.combined:
            parser.error("Indiquer --combined pour le rejeu ou --drive pour le robot")
        scans = load_acquisition(args.combined, args.single)
        replay_segmented(scans, args.output)


if __name__ == "__main__":
    main()
