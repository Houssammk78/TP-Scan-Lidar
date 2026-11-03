# TP Scan LiDAR - TP1 avec quatre scans

Version actuelle : **quatre scans, 1821 mesures**, cartes individuelles et fusion.

- [Guide complet et limites](TP1_4_scans/README.md)
- [Fusion des quatre scans](TP1_4_scans/resultats/fusion_4_scans.png)
- [Carte vectorielle](TP1_4_scans/resultats/carte_vectorielle.png)
- [Carte occupation](TP1_4_scans/resultats/grid_map_finale.png)
- [Progression de la grille](TP1_4_scans/resultats/grid_map_progression.png)
- [Scans sources](TP1_4_scans/data)
- [Resultats CSV et metadonnees](TP1_4_scans/resultats)

Installer Python 3 (avec Tk pour les fenetres), puis :

    python -m pip install -r LD06_Atelier/requirements.txt

Ouvrir les lanceurs dans TP1_4_scans pour visualiser les quatre scans, la carte
vectorielle ou la grille, et modifier independamment les poses.

    python TP1_4_scans/generer.py
    python -m unittest discover -s LD06_Atelier -p "test_*.py" -v

Le rendu remplace les anciennes cartes a deux scans. Les anciens resultats restent
dans l'historique Git. Aucun force-push n'est utilise.

**Qualite** : le scan 4 s'aligne tres bien sur le scan 3 (environ 99% de voisins
sous 20 cm), le scan 1 partiellement (72%), le scan 2 moins bien (37%). Les hauteurs
des scans 1 et 2 sont inconnues ; celle du scan 4 est supposee egale a 1,90 m.
Les cartes fusionnees restent des estimations, pas un plan de la salle valide.
