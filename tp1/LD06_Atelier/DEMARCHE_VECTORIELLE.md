# Carte vectorielle - TP Jour 1

Lancement : double-cliquer sur Lancer_Carte_Vectorielle.bat, ou :

    python LD06_Atelier/viewer.py --vector-map

Export sans fenetre :

    python LD06_Atelier/viewer.py --vector-map --no-show --save carte_vectorielle.png

Les points sources sont colores par scan. Les segments de la carte sont roses.
Les curseurs de pose reconstruisent la carte depuis les scans sources, dans leur ordre.
Le bouton Exporter segments enregistre les poses courantes dans carte_vectorielle.csv
(coordonnees des segments), sans modifier les scans. Enregistrer poses sauvegarde
separement les reglages de position et d'orientation dans poses.json.

## Choix techniques et demarche

1. Lecture des coordonnees cartesiennes fournies dans les CSV ; mm vers metres.
   Les CSV utilises emploient Y = -r sin(angle), contrairement au repere polaire
   mathematique habituel. On conserve ce Y pour rester coherent avec la fusion.
2. Filtrage geometrique : points finis, distances locales entre 0.15 et 12 m.
   Les points invalides interrompent les groupes. Pas de seuil d'intensite :
   ce lecteur ne charge pas cette colonne, et aucun seuil qualite n'est calibre.
3. Groupes consecutifs en ordre d'acquisition, coupure au-dela de 0.32 m.
   Le premier et le dernier groupe ne sont pas raccordes a travers 0 degre.
4. Extraction split-and-fit : droite par PCA/SVD, erreur perpendiculaire maximale
   0.06 m ; division selon la corde aux changements de direction.
   Au moins 5 points et 0.20 m de longueur. Les groupes trop petits sont rejetes.
5. Passage au repere global : Pglobal = R(angle) Plocal + [x,y].
   Les poses chargees sont les estimations precedentes, pas une verite terrain.
6. Association : angle non oriente <= 8 degres, distance entre droites supports
   aux milieux <= 0.15 m, ecart projete <= 0.25 m.
   Fusion par ajustement PCA des quatre extremites ; pas de ponderation par
   le nombre de points. Le compteur observations compte les primitives fusionnees.
7. Avant l'ajout du nouveau scan, les rayons capteur-impact sont raccourcis de
   0.15 m pour preserver les surfaces d'impact. Les anciens segments traverses
   sont decoupes en conservant leur plus long cote, puis elimines si < 0.20 m.
   Cette simplification suit le TP : elle ne represente pas une ouverture complete.
8. Export CSV : x1_m, y1_m, x2_m, y2_m, observations, last_seen (numero du scan).

## Operations geometriques et tolerance

vector_map.py expose angle_between, are_close, merge_segments, intersection,
cut_longest, extract_segments et VectorMap.update.
Tolerance spatiale EPS = 1e-8 m. Pour les parametres d'intersection, conversion
par longueur du segment. Parallelisme : seuil relatif 1e-12 sur les directions.
Intersection exigee sur les deux segments ; decoupage uniquement strictement
interieur au segment coupe. Une extremite du segment coupant peut toucher
l'interieur du segment coupe. Pas de decoupage colineaire. A longueurs egales
(a EPS pres), le cote contenant le premier point est conserve.

Tests : python -m unittest discover -s LD06_Atelier -p test_vector_map.py -v

## Limites et suite

Carte de segments uniquement : pas de cercles, pas de reconnaissance semantique
(mur/meuble), pas de SLAM ou de recalage automatique ajoute au viewer.
Avec seulement deux poses estimees, un ecart d'alignement peut creer des doublons
ou provoquer un decoupage errone. Les seuils sont ajustables dans les fonctions.
Les surfaces courbes et les petits objets sont simplifies ou rejetes.
Le nettoyage repose sur la longueur et les rayons, sans duree de vie temporelle.
La grid map demandee par le TP reste une etape distincte a implementer.
