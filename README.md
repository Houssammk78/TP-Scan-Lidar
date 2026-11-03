# Travaux pratiques LiDAR - EIGSI La Rochelle

**Houssam MAKHLOUK - Annee universitaire 2026/2027**

## TP1 : extraction, visualisation et cartographie

- [Rapport PDF](tp1/rapport_tp1.pdf) et [source LaTeX](tp1/rapport_tp1.tex).
- [Guide du TP1](tp1/README.md).
- [Donnees et cartes des quatre scans](tp1/TP1_4_scans).
- [Code et tests](tp1/LD06_Atelier).

## TP2 : localisation et scan matching

- [Rapport PDF](tp2/rapport_tp2.pdf) et [source LaTeX](tp2/rapport_tp2.tex).
- [Guide et protocole](tp2/README.md).
- [Réponses aux consignes, question par question](tp2/REPONSES_CONSIGNES.md).
- [Scans A/B et six acquisitions supplémentaires](tp2/acquisitions).
- [Resultats des 255 essais](tp2/resultats).
- [Diagnostics et 18 essais sur les nouveaux scans](tp2/resultats_nouveaux_scans).

Une methode pour chacun des trois supports : grille, segments et scan de reference.
En simulation : 60 essais par methode, tous reussis sur la scene simulee choisie,
avec seuils de 20 cm et 5 degres. Les scans reels n'ont pas de poses
terrain mesurees : leurs erreurs physiques et incertitudes ne sont pas inventees.

## Installation et tests

Depuis la racine du depot :

```powershell
python -m pip install -r tp1/LD06_Atelier/requirements.txt
python -m unittest discover -s tp1/LD06_Atelier -p "test_*.py" -v
python -m unittest discover -s tp2 -p "test_*.py" -v
python tp2/evaluer.py
python tp2/evaluer_nouveaux_scans.py
python tp2/creer_rapport.py
```

Les lanceurs du TP1 se trouvent dans tp1/TP1_4_scans ; celui du TP2 dans tp2.
21 tests TP1 et 11 tests TP2. Les chemins sont relatifs au depot pour permettre
le telechargement et la reproduction sur un autre poste.
