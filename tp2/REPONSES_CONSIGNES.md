# TP2 — Réponses aux consignes, question par question

Ce document distingue les **poses connues en simulation**, les **estimations
calculées sur les CSV** et les **mesures physiques**. Les mesures physiques de
déplacement et d'orientation n'ont pas été relevées pendant l'acquisition.

## 1. Localisation sur une grid map

**Méthode.** `grid_multiresolution` construit une grille d'occupation à partir
du scan de référence et de sa pose. Les cellules avant l'impact sont libres,
la cellule d'impact est occupée, les autres sont non observées. La résolution
est de 0,06 m. Pour une pose candidate, le solveur transforme le scan test et
minimise la distance des impacts aux cellules occupées par recherche
hiérarchique. Voir `localisation.py` et `tp1/LD06_Atelier/grid_map.py`.

**Couverture.** En simulation, les scans tests sont générés dans la scène
couverte par la carte. Sur les nouveaux scans réels, la comparaison N2–N5 est
exploratoire : le recouvrement mesuré est suffisant selon le critère ci-dessous,
mais ne certifie pas la couverture physique complète de la carte.

**Évaluation.** Sur 60 essais simulés avec pose vraie connue, l'erreur moyenne
est de 0,0145 m et 0,30°, avec 60/60 réussites selon les seuils ci-dessous.
Le temps médian de calcul est de 0,075 s par essai, hors construction de la
référence. Sur six départs identiques pour N2–N5, le temps médian est
environ 0,084 s. Aucune erreur métrique réelle ne peut être attribuée.

## 2. Localisation sur une carte vectorielle

**Méthode.** `vector_multiresolution` extrait des segments du scan de
référence, puis minimise la distance des points transformés aux segments.
La même recherche hiérarchique et les mêmes poses initiales que pour la
grille sont utilisées. Voir `localisation.py` et
`tp1/LD06_Atelier/vector_map.py`.

**Évaluation.** Sur les mêmes 60 essais simulés : erreur moyenne de 0,0074 m
et 0,375°, 60/60 réussites, temps médian 0,549 s. Sur N2–N5, le temps médian
est environ 0,294 s. Pour un départ à 180°, cette méthode donne environ
(0,19 m, -0,56 m, -98,25°), alors que les deux autres méthodes donnent une
orientation proche de -160°. Ce désaccord empêche de présenter une pose
réelle unique comme validée.

## 3. Localisation entre scans

**Méthode.** `scan_coarse_icp` recherche d'abord des poses candidates par
distance au scan de référence, puis affine les correspondances par ICP. La
méthode exige un recouvrement suffisant entre les deux acquisitions.

**Évaluation.** Sur les mêmes 60 essais simulés : erreur moyenne de 0,0107 m
et 0,375°, 60/60 réussites, temps médian 0,166 s. Sur N2–N5, le temps médian
est environ 0,128 s. Avec le départ (0,0,180°), la pose calculée est environ
(0,03 m, -1,11 m, -159,75°). C'est une **estimation de correspondance des
points**, pas une mesure physique indépendante.

## 4. Comparaison commune des méthodes

**Mêmes scans et mêmes départs.** La simulation utilise six scans tests et
dix poses initiales par scan, soit 60 essais par méthode. Le protocole réel
initial utilise les cinq scans tests A/B et cinq départs par scan. Les six
nouveaux CSV N1–N6 ont été inspectés deux à deux (15 paires). N4 est un scan
au sol ; N1, N2, N3, N5 et N6 ont été pris à une hauteur **estimée** entre
1,00 et 1,20 m, selon l'utilisateur. Ce n'est pas une mesure au centimètre.

**Critère de sélection réel.** Après alignement exploratoire, au moins 40 %
des points doivent être à moins de 20 cm **dans chaque sens**, et 70 % à
moins de 50 cm **dans chaque sens**. N2–N5 est la seule paire à hauteur
comparable qui franchit ces seuils. Sa sélection utilise le solveur entre
scans et peut favoriser cette méthode. Les autres scans restent conservés,
mais leur recouvrement ne permet pas une comparaison défendable avec ce
protocole. La carte ne doit pas être présentée comme une fusion complète de
la salle à partir de ces six scans.

Les trois méthodes ont été lancées sur N2–N5 avec exactement les six mêmes
départs : (0,0,0°), (0,5,-0,25,0°), (-0,5,0,3,0°), (0,0,90°), (0,0,180°)
et (0,0,-90°). Les résultats détaillés et les temps par essai figurent dans
`resultats_nouveaux_scans/comparaison_methodes.csv`.

| Départ | Grille : angle final | Segments : angle final | Entre scans : angle final |
| --- | ---: | ---: | ---: |
| 0° | 37,25° | -98,25° | 37,75° |
| 180° | -161,75° | -98,25° | -159,75° |

Les angles changent fortement selon l'initialisation et la représentation.
La scène observée comporte plusieurs alignements plausibles. Un faible coût
géométrique seul ne prouve pas la bonne localisation physique.

## 5. Erreur, réussite, temps et incertitude

**Seuils.** Un essai est réussi si l'erreur de position est au plus 0,20 m
**et** l'erreur angulaire au plus 5°. En simulation, les poses vraies sont
connues par construction : les erreurs et les taux de réussite ci-dessus
sont donc calculables. Les valeurs correspondent à une seule scène simulée.

**Sur robot.** Les positions et rotations de référence, ainsi que leurs
incertitudes, n'ont pas été mesurées indépendamment des scans. Les CSV ne
permettent pas de les reconstituer comme vérité terrain. Par conséquent, les
erreurs de position, les erreurs angulaires et les taux de réussite **réels**
restent non calculables et leurs colonnes sont vides. Les temps de calcul et
les scores de recouvrement sont mesurés, mais ne remplacent pas ces erreurs.
Pour les obtenir, il faut relever les poses des prises de vue avec un repère
de salle, un mètre et un instrument d'orientation, puis noter la précision
de ces relevés.

## Reproduire les résultats

Depuis la racine du dépôt :

```powershell
python tp2/evaluer.py
python tp2/evaluer_nouveaux_scans.py
python tp2/creer_rapport.py
python -m unittest discover -s tp2 -p "test_*.py" -v
```

`resultats/` contient les essais A/B et simulés. `resultats_nouveaux_scans/`
contient la qualité des six acquisitions, les 15 diagnostics de recouvrement,
les 18 essais de comparaison et les deux figures. Chaque tableau CSV possède
une variante `_Excel_FR.csv` à virgule décimale. Le rapport PDF se régénère
ensuite depuis le fichier LaTeX avec Tectonic ou une distribution LaTeX.
