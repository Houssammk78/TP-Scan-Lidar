"""Affiche les scans CSV et permet d'ajuster indépendamment leurs poses."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, RadioButtons, Slider
from matplotlib.collections import LineCollection

from geometry import apply_pose, load_scan
from vector_map import VectorMap
from grid_map import build_grid
from matplotlib.colors import ListedColormap, BoundaryNorm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scans", nargs="*", type=Path, default=[Path(__file__).parent.parent / "scan_20261102_170811_045727.csv", Path(__file__).parent.parent / "scan_20261102_170911_554109.csv"])
    parser.add_argument("--grid-map", action="store_true", help="Afficher la grille occupation")
    parser.add_argument("--resolution", type=float, default=0.05, help="Taille cellule en metres")
    parser.add_argument("--export-grid", type=Path, default=Path(__file__).parent / "grid_map")
    parser.add_argument("--vector-map", action="store_true", help="Construire une carte de segments")
    parser.add_argument("--export-vectors", type=Path, default=Path(__file__).parent / "carte_vectorielle.csv")
    parser.add_argument("--multicolor", action="store_true", help="Colorer selon la distance")
    parser.add_argument("--poses", type=Path, default=Path(__file__).parent / "poses.json")
    parser.add_argument("--save", type=Path, help="Enregistrer une image PNG")
    parser.add_argument("--no-show", action="store_true", help="Exporter sans ouvrir de fenêtre")
    args = parser.parse_args()
    if args.no_show:
        plt.switch_backend("Agg")
    if not np.isfinite(args.resolution) or args.resolution<=0:parser.error("Resolution strictement positive requise")
    if args.grid_map and args.vector_map:parser.error("Choisir --grid-map ou --vector-map")
    try:
        clouds = [load_scan(path) for path in args.scans]
        saved = json.loads(args.poses.read_text()) if args.poses.exists() else {}
        poses = []
        for path in args.scans:
            pose = saved.get(str(path.resolve()), saved.get(path.name, [0, 0, 0]))
            if len(pose) != 3 or not np.isfinite(pose).all():
                raise ValueError("Une pose doit contenir trois nombres finis")
            poses.append(list(map(float, pose)))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.error(str(error))

    fig, ax = plt.subplots(figsize=(11, 8))
    fig.subplots_adjust(left=0.09, right=0.72, bottom=0.29)
    artists, origins, arrows, contours = [], [], [], []
    colors = plt.get_cmap("turbo")(np.linspace(0.08, 0.92, len(clouds)))
    for i, (cloud, pose, color) in enumerate(zip(clouds, poses, colors)):
        points = apply_pose(cloud, *pose)
        lengths = np.linalg.norm(np.diff(cloud, axis=0), axis=1)
        ranges = np.linalg.norm(cloud, axis=1)
        mask = (lengths < 0.32) & (np.abs(np.diff(ranges)) < 0.25)
        line = LineCollection(np.stack([points[:-1], points[1:]], axis=1)[mask], colors=[color], linewidths=1.4, alpha=0.8)
        if args.multicolor:
            line.set_cmap('turbo'); line.set_clim(0, 12)
            line.set_array(((ranges[:-1]+ranges[1:])/2)[mask])
        ax.add_collection(line)
        contours.append((line,mask))
        artists.append(ax.scatter(points[:, 0], points[:, 1], s=9, c=(ranges if args.multicolor else [color]), edgecolors="none",
                                  label=f"Scan {i + 1} ({len(cloud)} points)"))
        if args.multicolor:
            artists[-1].set_array(ranges); artists[-1].set_cmap('turbo'); artists[-1].set_clim(0,12)
        origins.append(ax.plot(pose[0], pose[1], "+", color=color, markersize=12)[0])
        angle = np.deg2rad(pose[2])
        arrows.append(ax.quiver(pose[0], pose[1], np.cos(angle), np.sin(angle),
                               angles="xy", scale_units="xy", scale=2, color=color))
    ax.set(xlabel="X (m)", ylabel="Y (m)", title="LD06 Atelier - fusion estimee")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    status = fig.text(0.09, 0.025, "Alignement estime | Contours entre voisins | Croix = capteur", fontsize=9)

    if args.multicolor:
        bar = fig.colorbar(artists[0], ax=ax, fraction=0.04, pad=0.03)
        bar.set_label('Distance au capteur (m)')
    vector_artist = LineCollection([], colors="#d81b60", linewidths=2.8, zorder=5, label="Carte vectorielle")
    ax.add_collection(vector_artist)
    def rebuild_vectors(export=False):
        if not args.vector_map:return
        mapping=VectorMap()
        for cloud,pose in zip(clouds,poses):mapping.update(cloud,pose)
        vector_artist.set_segments([f['segment'] for f in mapping.features])
        status.set_text(f"Carte estimee : {len(mapping.features)} segments | X/Y en m | Poses ajustables")
        if export:
            mapping.export(args.export_vectors)
            status.set_text(f"{len(mapping.features)} segments exportes : {args.export_vectors.name}")
        return mapping
    rebuild_vectors()
    if args.vector_map:ax.legend(loc="upper left")
    grid_image = [None]
    def rebuild_grid(export=False):
        if not args.grid_map:return
        grid=build_grid(clouds,poses,args.resolution)
        if grid_image[0] is None:
            grid_image[0]=ax.imshow(grid.cells,origin="lower",extent=grid.extent,interpolation="nearest",cmap=ListedColormap(["#8d6e63","#81c784","#d32f2f"]),norm=BoundaryNorm([-1.5,-.5,50,100.5],3),zorder=0)
        else:
            grid_image[0].set_data(grid.cells);grid_image[0].set_extent(grid.extent)
        ax.set_title("LD06 Atelier - grille occupation estimee")
        status.set_text(f"Cellules {args.resolution:g} m | Marron=inconnu, vert=libre, rouge=occupe, bleu=capteur")
        if export:grid.export(args.export_grid)
        return grid
    rebuild_grid()
    if args.grid_map:
        for artist in artists:artist.set_visible(False)
        for line,mask in contours:line.set_visible(False)
        ax.grid(False)
        for i,origin_artist in enumerate(origins):
            origin_artist.set_label(f"Pose scan {i+1}")
            origin_artist.set_color("#1565ff")
            arrows[i].set_color("#1565ff")
        ax.legend(handles=origins,loc="upper left")
    active = [0]
    limit = max(20, max(abs(v) for pose in poses for v in pose[:2]) + 1)
    angle_limit = max(180, max(abs(pose[2]) for pose in poses))
    sliders = [
        Slider(fig.add_axes([0.16, 0.20, 0.5, 0.03]), "X (m)", -limit, limit, valinit=poses[0][0]),
        Slider(fig.add_axes([0.16, 0.14, 0.5, 0.03]), "Y (m)", -limit, limit, valinit=poses[0][1]),
        Slider(fig.add_axes([0.16, 0.08, 0.5, 0.03]), "θ (°)", -angle_limit, angle_limit,
               valinit=poses[0][2]),
    ]
    labels = [f"Scan {i + 1}" for i in range(len(clouds))]
    radio = RadioButtons(fig.add_axes([0.76, 0.43, 0.21, 0.42]), labels)
    fig.text(0.76, 0.88, "Choisir le scan à déplacer", fontsize=9)

    def fit(_event=None):
        points = np.concatenate([apply_pose(c, *p) for c, p in zip(clouds, poses)])
        low, high = points.min(axis=0), points.max(axis=0)
        margin = max(0.5, float(np.max(high - low)) * 0.05)
        ax.set_xlim(low[0] - margin, high[0] + margin)
        ax.set_ylim(low[1] - margin, high[1] + margin)
        fig.canvas.draw_idle()

    def update(_value):
        i = active[0]
        pose = [slider.val for slider in sliders]
        poses[i] = pose
        points = apply_pose(clouds[i], *pose)
        artists[i].set_offsets(points)
        line, mask = contours[i]
        line.set_segments(np.stack([points[:-1], points[1:]], axis=1)[mask])
        origins[i].set_data([pose[0]], [pose[1]])
        arrows[i].set_offsets([[pose[0], pose[1]]])
        angle = np.deg2rad(pose[2])
        arrows[i].set_UVC(np.cos(angle), np.sin(angle))
        rebuild_vectors()
        rebuild_grid()
        fig.canvas.draw_idle()

    def select(label):
        active[0] = labels.index(label)
        for slider, value in zip(sliders, poses[active[0]]):
            slider.eventson = False
            slider.set_val(value)
            slider.eventson = True
        fig.canvas.draw_idle()

    def save_poses(_event):
        saved.update({path.name: pose for path, pose in zip(args.scans, poses)})
        try:
            args.poses.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
            status.set_text(f"Poses enregistrées : {args.poses}")
        except OSError as error:
            status.set_text(f"Erreur d'enregistrement : {error}")
        fig.canvas.draw_idle()

    for slider in sliders:
        slider.on_changed(update)
    radio.on_clicked(select)
    save_button = Button(fig.add_axes([0.76, 0.24, 0.21, 0.06]), "Enregistrer poses")
    save_button.on_clicked(save_poses)
    fit_button = Button(fig.add_axes([0.76, 0.15, 0.21, 0.06]), "Recentrer")
    fit_button.on_clicked(fit)
    if args.vector_map:
        export_button = Button(fig.add_axes([0.76, 0.06, 0.21, 0.06]), "Exporter segments")
        export_button.on_clicked(lambda event: (rebuild_vectors(True),fig.canvas.draw_idle()))
        rebuild_vectors(True)
    if args.grid_map:
        grid_button = Button(fig.add_axes([0.76, 0.06, 0.21, 0.06]), "Exporter grille")
        grid_button.on_clicked(lambda event: (rebuild_grid(True),fig.canvas.draw_idle()))
        rebuild_grid(True)
    fit()
    if args.save:
        fig.savefig(args.save, dpi=150)
        print(f"Image enregistrée : {args.save}")
    if not args.no_show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
