# TP Scan LiDAR - Jour 1

Outils Python de visualisation et de cartographie a partir de scans LD06 reels.

## Installation et utilisation

Installer Python 3 avec le support Tk pour les fenetres Matplotlib, puis depuis
le dossier du depot :

```powershell
python -m pip install -r LD06_Atelier/requirements.txt
python LD06_Atelier/viewer.py
python LD06_Atelier/viewer.py --vector-map
python LD06_Atelier/viewer.py --grid-map
```

Les lanceurs .bat du dossier LD06_Atelier proposent les memes modes sous Windows.
Le mode normal distingue les scans par couleur ; --multicolor colore par distance.
Selectionner un scan a droite, ajuster X/Y (m) et theta (degres), puis enregistrer
les poses. Exporter segments/grille sauvegarde la carte correspondante.
Les poses sont referencees par nom de fichier pour fonctionner sur un autre PC.

## Donnees et conventions

Les deux fichiers scan_20261102_*.csv sont les mesures sources utilisees :
point_index, angle_deg, dist_mm, intensity, x_lib_mm, y_lib_mm.
Les scans XLSX de l'etudiant sont egalement disponibles dans le depot.
Les fichiers sources ne sont pas modifies par le viewer.
Conversion mm vers m. Dans ces sources Y=-r*sin(angle) : cette convention est
conservee, puis chaque pose applique une rotation et une translation.

L'acquisition a precede ces outils. Ce depot ne fournit pas de programme de
capture serie verifie : le port, le montage et le logiciel effectivement utilises
pour les acquisitions doivent etre decrits par l'etudiant. Chaque etudiant doit
confirmer qu'il fournit ses propres scans reels, comme demande dans le TP.

## Resultats et explications

- Carte vectorielle : carte_vectorielle.csv et carte_vectorielle.png.
- Grid map : grid_map.csv et grid_map_finale.png (cellules de 5 cm).
- Progression des observations : grid_map_progression.png.
- [Demarche vectorielle](LD06_Atelier/DEMARCHE_VECTORIELLE.md).
- [Demarche grid map](LD06_Atelier/DEMARCHE_GRID_MAP.md).
- [Bilan du TP et limites](BILAN_TP.md).

Grid map : marron inconnu, vert libre, rouge occupe, bleu position capteur.
Le CSV est une matrice ; son origine, sa resolution et sa convention de lignes
sont dans LD06_Atelier/grid_map.json. Le NPZ permet de recharger puis mettre a jour
une grille existante avec GridMap.load(...).update(scan, pose).

## Verification et reproduction

```powershell
python -m unittest discover -s LD06_Atelier -p "test_*.py" -v
python LD06_Atelier/viewer.py --vector-map --no-show --save carte_vectorielle.png
python LD06_Atelier/export_grid_figures.py
```

21 tests : geometrie des segments et cas limites de decoupage, rayons et mise a
jour de grille, sauvegarde/rechargement, callbacks du viewer (selection, curseurs,
sauvegarde des poses, exports). Les callbacks sont testes sans fenetre ; ils ne
remplacent pas une verification du rendu et des clics sur chaque poste.

## Limite principale

Les poses sont estimees et ajustees manuellement : les cartes ne sont pas des
plans metriques valides de la salle. Aucun SLAM ni localisation automatique du
robot n'est implemente dans ce rendu. Les zones inconnues restent inconnues,
sans remplissage artificiel entre les faisceaux.
