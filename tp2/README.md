# TP2 — Localisation par scan matching

Ce dossier couvre les trois références exigées : une grille d'occupation,
une carte vectorielle et un autre scan. Les six acquisitions LD06 de A/B,
six acquisitions supplémentaires N1 à N6, les scripts, les essais chiffrés
et le rapport sont conservés ici. Les réponses aux consignes sont présentées
[question par question](REPONSES_CONSIGNES.md).

## Reproduire

Depuis la racine du dépôt, avec Python et les dépendances du TP1 :

    python -m pip install -r tp1/LD06_Atelier/requirements.txt
    python tp2/evaluer.py
    python tp2/evaluer_nouveaux_scans.py
    python tp2/creer_rapport.py
    python -m unittest discover -s tp2 -p "test_*.py" -v

Le rapport PDF est dans [rapport/rapport_tp2.pdf](rapport/rapport_tp2.pdf) ; sa source LaTeX
est [rapport/rapport_tp2.tex](rapport/rapport_tp2.tex). LaTeX n'est requis que pour
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

La [synthèse des poses estimées](resultats/poses_estimees_csv.csv) donne,
depuis le départ nul, la médiane des trois méthodes pour A_02, A_03 et
B_01 à B_03. Les trois scans B se placent près de
(-0,89 m ; -0,04 m ; -1°) par rapport à A_01. Les écarts entre méthodes
sont indiqués séparément et ne mesurent pas l'incertitude physique.

Les acquisitions réelles n'ont pas de déplacement, angle et incertitude
mesurés indépendamment. Les colonnes d'erreur et de réussite réelles restent
vides ; un faible résidu ou un accord entre méthodes ne prouve pas la justesse
physique. Le fichier [references_mesurees.csv](references_mesurees.csv)
permet de compléter ces mesures. Pour chaque scan de test, saisir la pose
relative à A_01 et les deux incertitudes :

    scan;x_m;y_m;angle_deg;uncertainty_position_m;uncertainty_angle_deg
    B_01;<x mesure>;<y mesure>;<angle mesure>;<incertitude position>;<incertitude angle>

Cette ligne est un **gabarit**, pas une mesure du projet : ne la copier qu'après
avoir remplacé les cinq champs par des valeurs relevées sur place.
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

## Six acquisitions supplémentaires

Les six nouveaux CSV sont dans `acquisitions/scan_20261103_15*`, chacun avec
la capture brute, l'aperçu et les métadonnées d'acquisition. N1, N2, N3,
N5 et N6 ont été pris à une hauteur **estimée entre 1,00 et 1,20 m** ; N4
a été pris au sol. Ce dernier reste visible dans les diagnostics et n'est
pas mêlé aux comparaisons à hauteur commune.

`evaluer_nouveaux_scans.py` diagnostique les 15 paires avec un recouvrement
dans les deux sens. Le critère déclaré dans
`resultats_nouveaux_scans/protocole_nouveaux_scans.json` retient N2–N5 pour
les trois méthodes, avec six poses initiales strictement communes (18 essais).
La sélection est exploratoire et peut favoriser la méthode entre scans qui
sert au diagnostic. Elle ne fournit pas une pose terrain certifiée.

Les fichiers de `resultats_nouveaux_scans/` donnent les diagnostics, les
estimations, les temps et les deux figures. Les colonnes d'erreur et de
réussite restent vides sur ces scans réels : les déplacements, rotations et
leurs incertitudes n'ont pas été mesurés indépendamment des CSV. Le rapport
LaTeX/PDF utilise ces résultats et décrit les limites de l'alignement.
