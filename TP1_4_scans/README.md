# TP1 - quatre scans LD06

## Donnees

| Scan | Origine | Points | Hauteur |
|---|---|---:|---|
| 1 | scan_20261102_170811_045727.csv | 454 | inconnue |
| 2 | scan_20261102_170911_554109.csv | 454 | inconnue |
| 3 | acquisition COM3 du 03/11/2026, 11:13 | 456 | 1,90 m annoncee |
| 4 | acquisition COM3 du 03/11/2026, 11:15 | 457 | 1,90 m supposee, a confirmer |

Les quatre CSV sources sont dans data/ et restent inchanges par les outils.
Nouvelles acquisitions via ESP32 : port COM3, 115200 bauds, sortie CSV du firmware.
Selection d'un tour par indices consecutifs et couverture angulaire >=350 degres.
La procedure exacte et la hauteur des deux anciens scans restent a confirmer.

## Installation et lancement

Depuis la racine du depot :

    python -m pip install -r LD06_Atelier/requirements.txt

Sous Windows, ouvrir TP1_4_scans puis double-cliquer :
- Lancer_4_Scans.bat : nuages de points de quatre couleurs, poses ajustables.
- Lancer_Vectorielle.bat : segments consolides et export CSV.
- Lancer_Grid_Map.bat : occupation et export CSV/JSON/NPZ.

Selectionner le scan puis modifier X/Y (m) et angle (degres). Enregistrer poses
conserve les reglages ; Exporter sauvegarde la carte de la fenetre.
Les lanceurs utilisent les poses a quatre scans, et non les anciennes poses.

## Reproduire les resultats

    python TP1_4_scans/recaler.py
    python TP1_4_scans/generer.py
    python -m unittest discover -s LD06_Atelier -p "test_*.py" -v

recaler.py recalcule les poses estimees ; generer.py regenere les images et CSV
avec les poses enregistrees (y compris les reglages manuels sauvegardes).
Les resultats principaux sont dans resultats/ :
- fusion_4_scans.png et .csv : 1821 mesures, sources identifiees, coordonnees locales
  conservees et coordonnees globales corrigees ; format Excel francais.
- carte_vectorielle.png et .csv : 38 segments consolides pour les poses livrees.
- grid_map_finale.png et grid_map.csv/.json/.npz : grille 5 cm, 288 lignes x 270 colonnes.
- grid_map_progression.png : mises a jour successives scan 1, puis 2, puis 3, puis 4.
- grilles_individuelles.png et vectorielles_individuelles.png : quatre vues locales.
- grid_scanN.* et vectorielle_scanN.* : exports individuels.
- alignement.json : mesures de coherence du recalage.

## Recalage et limites importantes

Le scan 3 sert de repere fixe. Recalage ICP robuste multi-departs : 36 rotations,
9 translations initiales par rotation, conservation de 65% des correspondances
les plus proches a chaque iteration. Selection selon distance symetrique plafonnee.
Aucun mur n'est ajoute a partir d'un dessin. Les points bruts sont conserves.

Correspondances source -> scan 3 a moins de 20 cm :
- scan 1 : environ 72% ;
- scan 2 : environ 37% ;
- scan 4 : environ 99%.

Ce sont des indicateurs de superposition, pas des erreurs de pose mesurees.
La recherche retrouve pour le scan 4 une rotation d'environ -90 degres et une
translation d'environ 4 cm par rapport au scan 3 : il semble apporter surtout
une nouvelle orientation plutot qu'un grand deplacement. A confirmer sur le terrain.
La rotation libre a ete retenue car l'hypothese d'orientation identique donnait
une mauvaise superposition. Les dimensions globales ne sont pas validees au metre.
Le scan 2, les hauteurs inconnues et les occultations empechent de garantir un
alignement correct de tous les obstacles interieurs. Des murs communs coexistent
avec des objets visibles a des hauteurs differentes : ne pas les confondre.

## Choix cartographiques

Grid map : -1 inconnu (marron), 0 libre (vert), 100 occupe (rouge), capteur bleu.
Bresenham libere les cellules avant l'impact ; impact prioritaire dans un scan.
Les quatre scans mettent a jour le meme objet dans l'ordre 1,2,3,4.
Une observation recente peut effacer une ancienne ; avec des hauteurs differentes,
la grille fusionnee est une demonstration, pas une garantie d'espace navigable
pour un robot. Les grilles individuelles restent disponibles pour comparaison.

Vectorielle : groupes par proximite, split-and-fit, fusion selon orientation,
distance aux droites et ecart des extremites. Sur ce lot, pas d'effacement des
anciens segments par les rayons des autres scans : on ignore leur meme hauteur.
Le viewer utilise --keep-vector-features pour reproduire ce choix.
La mise a jour avec effacement reste disponible dans le mode normal du viewer
et dans VectorMap.update ; elle est testee pour le TP.

Details des seuils et cas limites : voir les deux documents DEMARCHE dans
LD06_Atelier. Les options de confiance, probabilites et duree de vie sont facultatives.
