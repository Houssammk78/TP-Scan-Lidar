# TP3 — localisation et cartographie simultanées (début de SLAM)

Ce dossier contient une intégration **hors ligne** des outils du TP1 et du TP2.
Après chaque localisation, le scan est ajouté à la grid map et à la carte
vectorielle. La séquence utilise les quatre scans TP1 et les trois tours des
positions A et B du TP2 (dix scans candidats, hauteur annoncée de 1,90 m).
Le scan TP1 n° 3 fixe le repère. Les poses initiales viennent des estimations
TP1 et TP2 ; elles ne constituent pas une vérité terrain mesurée.

## Exécution

Depuis la racine du dépôt :

```powershell
python -m pip install -r tp1/LD06_Atelier/requirements.txt
python tp3/slam.py
python tp3/creer_rapport.py
```

Pour compiler le rapport, lancer `tectonic rapport_tp3.tex` depuis
`tp3/rapport` (ou un autre compilateur LaTeX compatible). Les fichiers
livrés sont le [PDF](rapport/rapport_tp3.pdf) et la
[source LaTeX](rapport/rapport_tp3.tex).

## Résultats

- [Carte finale](resultats/carte_finale.png) : grille, points, segments et poses.
- [Carte exploratoire](resultats/carte_exploratoire.png) : ajoute aussi le scan
  refusé par le contrôle de qualité ; elle reste provisoire.
- [Progression](resultats/progression.png) : carte après chaque scan accepté.
- [Grille](resultats/grid_map.npz), [métadonnées](resultats/grid_map.json)
  et [CSV](resultats/grid_map.csv) : carte d'occupation ternaire.
- [Segments](resultats/carte_vectorielle.csv) et
  [points fusionnés](resultats/points_fusionnes.csv).
- [Poses et contrôles](resultats/poses_et_qualite.csv) et
  [diagnostic détaillé](resultats/diagnostic.json).

La méthode entre scans est la recherche multirésolution suivie d'ICP du TP2.
La référence grandit après chaque scan accepté. Un scan avec un recouvrement
ou une cohérence insuffisants est écarté au lieu de déformer la carte.
Les scans N1–N6 ne sont pas superposés à la coupe de 1,90 m : N1/N2/N3/N5/N6
ont une hauteur estimée de 1,00 à 1,20 m et N4 a été pris au sol.

**Limite :** cette carte est une estimation des surfaces observées. Les
positions physiques des acquisitions et les dimensions de la salle n'ont pas
été relevées indépendamment. La couverture de toute la salle et l'erreur
géométrique absolue ne peuvent donc pas être certifiées avec ces CSV seuls.
Le déplacement automatique du robot est un bonus non implémenté ici.
