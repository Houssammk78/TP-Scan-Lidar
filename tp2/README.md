# TP2 - Localisation / Scan matching

## Lancer

Depuis la racine du projet :

    python tp2/evaluer.py
    python -m unittest discover -s tp2 -p "test_*.py" -v

Dependances : numpy et matplotlib, comme pour le TP1. Les modules du TP1 dans
tp1/LD06_Atelier sont reutilises pour lire les CSV, construire les cartes et appliquer
les poses. Aucun materiel branche n'est necessaire pour rejouer les essais.

Essai individuel :

    python tp2/localiser.py --reference tp2/acquisitions/position_A_20261103_120212/A_01.csv --scan tp2/acquisitions/position_B_20261103_120333/B_01.csv --method scan_icp --initial 0 0 0 --output tp2/resultats/pose_B01.json

Autres choix : grid_multiresolution, vector_multiresolution.
Unites des poses : X/Y en metres, orientation en degres.
Les figures et CSV sont dans resultats/. Le rapport explique les choix en detail.

## Trois references et trois methodes

- Grid map : reference construite a partir de A_01 seulement, cellules de 6 cm.
  Champ des distances aux centres des cellules occupees, puis recherche multiresolution.
- Carte vectorielle : extraction de segments de A_01 seulement, distance exacte
  point-segment, puis la meme recherche multiresolution.
- Entre scans : reference A_01, ICP point-a-point avec 85% des correspondances.

A_02, A_03 et B_01..03 ne construisent pas la reference. En simulation, le scan de
reference et les deux scans de test sont generes independamment par raycasting,
avec poses exactes et bruit gaussien de distance (sigma 8 mm). L'environnement
asymetrique comprend murs, decrochement et deux obstacles rectangulaires.

Les trois methodes recoivent les memes scans, le meme sous-echantillonnage (un point
sur trois apres filtre) et les memes poses initiales. Plage de portee 0.15-12 m.
References prepares une fois ; temps de preparation et de recherche distingues.
Le nombre de points de reference et la representation sont propres a chaque methode.

## Protocole chiffre

Simulation : 2 poses de test x 10 perturbations initiales x 3 methodes = 60 essais.
Scans reels : 5 scans de test x 5 perturbations initiales x 3 methodes = 75 essais.
Total 135 essais. Graines fixes 11,20,21 pour reproduire les donnees simulees.

Les erreurs initiales simulees sont ajoutees aux poses exactes uniquement pour
construire des cas de test controles. Les solveurs ne recoivent pas la pose exacte.
En reel, les poses initiales sont les memes decalages autour de (0,0,0).
Les cartes sont construites a partir d'un scan et ne couvrent que les surfaces
visibles depuis celui-ci. Les essais voisins voient largement ces memes surfaces,
mais certains obstacles restent occultes.

Reussite : erreur de position <=0.20 m ET erreur angulaire <=5 degres.
Angle ramene a [-180,180[. Temps mesure par perf_counter, hors preparation.
Les statistiques incluent tous les essais, y compris les echecs difficiles.
Le taux de reussite repose sur un petit ensemble synthetique (20 essais par methode),
pas sur une certification generalisable a toutes les salles.

Multiresolution : pas successifs (0.5 m,10 deg), (0.15 m,3 deg), (0.04 m,1 deg),
(0.01 m,0.25 deg), recherche +/-2 pas a chaque niveau ; trois meilleurs candidats
conserves pour raffinement. Plage maximale theorique : +/-1.4 m et +/-28.5 deg
par rapport au depart ; les perturbations plus grandes sont volontairement difficiles.
Score : moyenne des distances au carre plafonnees a 0.6 m (limite les outliers).
Grille hors carte : distance 1 m, plafonnee dans le score ; aucune extrapolation.
La discretisation du champ impose un plancher de precision a la methode grille.
ICP : maximum 70 iterations, sous-ensemble de 85% des correspondances, seuils
1e-5 m et 1e-4 deg sur l'increment. Sensible aux minima locaux et aux symetries.

## Resultats

La synthese CSV et le JSON stockent les valeurs calculees, pas des objectifs annonces.
Sur ce jeu : 70% de reussite pour grille/segments et 80% pour ICP en simulation.
Les initialisations proches reussissent ; les grandes erreurs peuvent sortir du
bassin de convergence. Les moyennes d'erreur incluent ces echecs.

Reel : les methodes donnent pour B_01 depuis (0,0,0) des translations proches de
-0.9 m en X dans le repere de A_01, mais ni distance ni rotation n'ont ete mesurees.
Les fichiers indiquent donc NULL pour erreurs et taux de reussite reels, et pour
l'incertitude de la reference terrain. La dispersion algorithmique ou le residu
ne remplace pas une incertitude de mesure physique. Aucun taux de reussite reel
n'est invente. Hauteur A : 190 cm annoncee ; B : meme hauteur supposee selon protocole.
L'incertitude de hauteur et l'immobilite ne sont pas mesurees.

## Lecture des exports

- essais.csv : toutes les poses initiales/finales, erreurs, scores et temps.
- synthese.csv : comparaison des trois methodes, simulation et reel separes.
- protocole_et_resultats.json : seuils, perturbations, poses exactes et limites.
- comparaison_simulation.png : distributions des erreurs et temps.
- sensibilite_initialisation.png : taux de reussite par perturbation (2 cas seulement).
- simulation_localisation.png : exemple des trois alignements simules.
- localisation_reelle.png : alignements A_02 et B_01 sur A_01, depart (0,0,0).
- reference_grid_*.npz/.csv/.json : cartes d'occupation utilisees.
- reference_segments_simulation.csv : segments de reference simules.

## Pour terminer l'evaluation sur robot

Les fonctions et les evaluations en simulation sont fournies. Il reste necessaire
pour une evaluation metrique sur robot de mesurer independamment les poses et de
documenter l'incertitude (distance, angle, montage). Une estimation ICP utilisee
comme verite terrain rendrait la comparaison circulaire. L'etudiant devra expliquer
cette limitation dans son rendu et, si exige par l'enseignant, completer l'acquisition.
