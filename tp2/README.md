# TP2 — Localisation par scan matching

Ce dossier couvre les trois références exigées : une grille d'occupation,
une carte vectorielle et un autre scan. Les six acquisitions LD06 de A/B,
les scripts, les essais chiffrés et le rapport sont conservés ici.

## Reproduire

Depuis la racine du dépôt, avec Python et les dépendances du TP1 :

    python -m pip install -r tp1/LD06_Atelier/requirements.txt
    python tp2/evaluer.py
    python tp2/creer_rapport.py
    python -m unittest discover -s tp2 -p "test_*.py" -v

Le rapport PDF est dans [rapport_tp2.pdf](rapport_tp2.pdf) ; sa source LaTeX
est [rapport_tp2.tex](rapport_tp2.tex). LaTeX n'est requis que pour
recompiler le PDF après avoir régénéré le fichier .tex.

Pour un scan individuel :

    python tp2/localiser.py --reference tp2/acquisitions/position_A_20261103_120212/A_01.csv --scan tp2/acquisitions/position_B_20261103_120333/B_01.csv --method scan_coarse_icp --initial 0 0 0 --output tp2/resultats/pose_B01.json

Autres méthodes : grid_multiresolution et vector_multiresolution.
X/Y sont en mètres et l'orientation en degrés.

## Références et méthodes

Le scan A_01 seul construit les trois références. Les cinq autres scans sont
des scans de test. En simulation, un scan de référence indépendant est
généré à (0,0,0), puis six scans tests à des poses connues. Les mêmes points,
le même filtrage et la même pose initiale servent aux trois méthodes pour
chaque essai.

- **Grille** : carte ternaire de 6 cm issue de A_01, champ des distances aux
  cellules occupées, recherche hiérarchique de la pose.
- **Segments** : carte vectorielle extraite de A_01, distance exacte entre
  points et segments, même recherche.
- **Entre scans** : recherche hiérarchique par distance au scan de référence,
  puis ICP point-à-point. Le champ de distance interpolé accélère la recherche ;
  l'ICP utilise les vrais points du scan.

La recherche couvre initialement ±2,5 m selon X et Y et ±100° autour du
départ. Les 120 meilleurs candidats sont réévalués avec tous les points,
et huit hypothèses distinctes sont affinées à trois résolutions plus fines.
La portée théorique finale est ±2,90 m et ±108,5°. La fonction coût est la
moyenne des distances au carré plafonnées à 0,6 m. Le capteur est filtré à
0,15–12 m ; un point sur trois est retenu pour les essais.

## Évaluation

La simulation teste six scans × dix perturbations initiales × trois méthodes.
Le réel teste cinq scans × cinq perturbations × trois méthodes.
L'erreur de position et l'erreur d'orientation sont calculées seulement
lorsqu'une pose de référence indépendante est connue. Les seuils de réussite
sont 0,20 m **et** 5°. Les temps de préparation des références et ceux des
solveurs sont séparés dans le CSV.

Les acquisitions réelles n'ont pas de déplacement, angle et incertitude
mesurés indépendamment. Les colonnes d'erreur et de réussite réelles restent
vides ; un faible résidu ou un accord entre méthodes ne prouve pas la justesse
physique. Le fichier [references_mesurees.csv](references_mesurees.csv)
permet de compléter ces mesures. Pour chaque scan de test, saisir la pose
relative à A_01 et les deux incertitudes :

    scan;x_m;y_m;angle_deg;uncertainty_position_m;uncertainty_angle_deg
    B_01;-0,90;0,00;0,00;0,05;2,00

Cette ligne n'est qu'un **exemple de format**, pas une mesure du projet.
Les champs vides sont ignorés. Une ligne partiellement remplie est rejetée.
Après mesures, relancer la commande :

    python tp2/evaluer.py --mesures tp2/references_mesurees.csv

Puis régénérer le rapport.

Le fichier resultats/essais.csv contient chaque départ, pose finale, erreur
éventuelle, score et temps. resultats/synthese.csv résume par méthode.
resultats/repetabilite_reelle.csv mesure la dispersion entre acquisitions
de A et de B depuis le départ nul ; ce n'est pas une incertitude terrain.
Chaque CSV a aussi une version _Excel_FR.csv à séparateur point-virgule
et virgule décimale.

Les cartes, les figures et le protocole JSON sont dans resultats/.
Les temps varient avec la machine et la simulation utilise un seul type de
pièce. Les cartes réelles ne contiennent que ce que A_01 a observé.
