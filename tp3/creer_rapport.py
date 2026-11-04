"""Génère le rapport LaTeX TP3 à partir du diagnostic effectivement calculé."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "resultats" / "diagnostic.json").read_text(encoding="utf-8"))
REPORT = ROOT / "rapport"
REPORT.mkdir(exist_ok=True)


def tex(value):
    return str(value).replace("_", r"\_")


rows = []
for item in DATA["scans"]:
    x, y, a = item["pose_estimee"]
    q = item["quality"]["within_30cm"]
    rows.append(
        f"{tex(item['scan'])} & {item['points']} & {x:.2f} & {y:.2f} & {a:.1f} & "
        + ("--" if q is None else f"{100*q:.0f}\\%")
        + f" & {item['matching']['score']:.3f} & "
        + ("Ajouté" if item["status"] == "ajoute" else "Écarté") + r" \\"
    )

def format_rows():
    return "\n".join(rows)


accepted = [item for item in DATA["scans"] if item["status"] == "ajoute"]
rejected = [item["scan"] for item in DATA["scans"] if item["status"] != "ajoute"]
points = sum(item["points"] for item in accepted)
extent = DATA["grid_extent_m"]

template = r"""
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage[margin=2.1cm]{geometry}
\usepackage{amsmath,graphicx,booktabs,float,longtable}
\usepackage[hidelinks]{hyperref}
\graphicspath{{../resultats/}}
\hypersetup{pdfauthor={Houssam MAKHLOUK},pdftitle={TP3 - Intégration SLAM et cartographie}}
\begin{document}
\hypersetup{pageanchor=false}
\begin{titlepage}\centering
\vspace*{1cm}{\Large\bfseries EIGSI\par}
\vspace{.4cm}{\large Année universitaire 2026/2027\par}
\vspace{2cm}{\large RAPPORT DE TRAVAUX PRATIQUES\par}
\vspace{.8cm}\rule{.9\textwidth}{1pt}\par\vspace{.6cm}
{\Huge\bfseries TP -- Jour 3\par}\vspace{.6cm}
{\LARGE Intégration SLAM et cartographie de la salle\par}
\vspace{.6cm}\rule{.9\textwidth}{1pt}
\vfill{\large Réalisé par\par}\vspace{.3cm}
{\LARGE\bfseries Houssam MAKHLOUK\par}
\vspace{.4cm}{\large Étudiant à EIGSI\par}
\vfill
\end{titlepage}
\pagenumbering{roman}\hypersetup{pageanchor=true}
\tableofcontents\clearpage\pagenumbering{arabic}

\section{Objectif et continuité des TP}
Le TP1 fournit la lecture des CSV, la conversion des coordonnées, une grille
d'occupation et une carte vectorielle. Le TP2 fournit la localisation entre
scans. Ce TP3 les enchaîne : après chaque estimation de pose, le nouveau scan
est projeté dans le repère global et inséré dans les deux cartes. Le rejeu
est incrémental : le scan courant n'utilise que la carte construite avec les
scans précédents. Il s'agit d'un début de SLAM sur des scans enregistrés. La carte n'est pas corrigée par
fermeture de boucle ni par optimisation globale des poses.

\section{Données, sélection et repères}
Le lot sélectionné comprend quatre scans du TP1 et les trois tours A et B du
TP2, soit @@TOTAL@@ scans. Ils sont annoncés à une même hauteur de 1,90 m dans
les métadonnées ou le protocole. Cette hauteur n'a pas été mesurée par le
LiDAR. Les acquisitions N1, N2, N3, N5 et N6 ont une hauteur estimée entre
1,00 et 1,20 m ; N4 a été pris au sol. Ces acquisitions restent disponibles
dans le TP2, mais ne sont pas superposées à cette coupe 2D.

Le scan 1 du TP1 fixe le repère $(0,0,0^\circ)$. Les scans sont rejoués dans
l'ordre d'acquisition. Aucune pose sauvegardée
des TP1 et TP2 n'est utilisée pour localiser les scans suivants. Les poses
initiales sont générées avec la dernière pose estimée et les centres des
nuages pour quatre orientations candidates. Les fichiers sources et leurs coordonnées locales sont
conservés ; les coordonnées globales produites sont exportées séparément.

\section{Algorithme de localisation et de cartographie}
\subsection{Boucle scan par scan}
Pour chaque scan $S_k$, l'algorithme extrait les points valides entre 0,15 et
12 m. Les impacts déjà placés forment une référence croissante. La méthode
\texttt{scan\_coarse\_icp} du TP2 cherche la pose par recherche multirésolution,
puis affine par ICP. Le nuage de référence est réduit à un représentant par
cellule de 7 cm, puis au maximum à 700 points pour limiter le temps de calcul.
Cinq hypothèses initiales sont essayées : la dernière pose et quatre rotations
relatives à celle-ci, recentrées sur le nuage déjà cartographié. La pose au
coût le plus faible est évaluée avant chaque mise à jour de carte.

Un contrôle refuse l'ajout si moins de 32\% des points sont à 30 cm de la
référence ou si le score plafonné dépasse 0,11 m$^2$. Ces seuils servent
à limiter les fusions manifestement incompatibles ; ils ne démontrent pas
qu'une pose acceptée est géométriquement exacte.

\subsection{Mise à jour des cartes}
La grid map a une résolution de @@RES@@ m. Elle contient trois états : inconnu
$(-1)$, libre $(0)$ et occupé $(100)$. Chaque rayon marque les cellules
traversées comme libres et la cellule d'impact comme occupée. Le calcul utilise
la pose estimée pour le scan courant. La grille s'agrandit en cellules
inconnues lorsqu'un nouvel impact sort de ses bornes. La carte vectorielle extrait des segments
du scan local, les place dans le repère global et fusionne ceux qui sont
proches en position et orientation. Le découpage par rayons libres est désactivé
ici afin que de petites erreurs de pose ne suppriment pas les anciens segments.
Une mise à jour automatique de la géométrie des poses passées n'est pas faite.

\subsection{Contrôles reproductibles}
Un test de simulation utilise 80 points déterministes et une pose connue
$(0,70\,\mathrm{m},-0,35\,\mathrm{m},25^\circ)$. Le recalage retrouve cette pose
à moins de 0,03 m sur chaque coordonnée et 0,03$^\circ$ sur l'orientation.
Un second test vérifie l'agrandissement de la grille avant l'insertion d'un
rayon nouveau. Un rejeu de deux scans réels vérifie que les cartes et les
exports sont produits sans lecture des poses sauvegardées. Ces tests ne
remplacent pas une mesure indépendante dans la salle.

\section{Résultats calculés}
@@ACCEPTED@@ scans sur @@TOTAL@@ ont été ajoutés, soit @@POINTS@@ points
valides insérés. La carte vectorielle exportée contient @@SEGMENTS@@ segments.
La grille allouée couvre X de @@XMIN@@ à @@XMAX@@ m et Y de @@YMIN@@ à
@@YMAX@@ m ; ces bornes comprennent une marge de calcul et ne sont pas les
dimensions mesurées de la salle.

\begin{longtable}{lrrrrrrl}
\toprule Scan & Points & X (m) & Y (m) & $\theta$ ($^\circ$) & $<30$ cm & Score & Décision \\
\midrule\endhead
@@ROWS@@
\bottomrule
\end{longtable}
Les pourcentages comparent chaque scan au nuage cumulatif avant son insertion.
Le scan d'origine n'a pas de référence antérieure. Les scores ne sont pas des
erreurs de pose : les positions physiques n'ont pas été mesurées. Les temps et
scores détaillés sont dans \texttt{resultats/diagnostic.json} et
\texttt{resultats/poses\_et\_qualite.csv}. Le fichier @@REJECTED@@ a été écarté
par le contrôle de cohérence ; il reste conservé dans les données TP1.
Une seconde carte exploratoire ajoute ce scan pour montrer sa couverture
potentielle. Elle ne sert pas de résultat de référence, car son alignement
n'a pas passé le seuil de qualité choisi.

\begin{figure}[H]\centering
\includegraphics[width=.98\linewidth]{progression.png}
\caption{Construction progressive de la grid map. Chaque panneau montre la
carte après l'ajout d'un scan accepté. Blanc : inconnu ; vert : libre ; brun :
impact occupé.}
\end{figure}
\begin{figure}[H]\centering
\includegraphics[width=.95\linewidth]{carte_finale.png}
\caption{Carte finale issue des scans acceptés. Les points colorés indiquent
les impacts ; les lignes bleues sont les segments vectoriels ; les marqueurs
rouges montrent les poses estimées.}
\end{figure}
\begin{figure}[H]\centering
\includegraphics[width=.95\linewidth]{carte_exploratoire.png}
\caption{Carte exploratoire avec le scan écarté. La zone supplémentaire et ses
segments sont provisoires, faute de validation indépendante du recalage.}
\end{figure}

\section{Limites et suite du travail}
Les scans n'ont pas de poses terrain ni d'incertitudes de position et d'angle
mesurées indépendamment. On ne peut donc calculer ni erreur physique de la
carte ni taux de réussite réel. La répétition des tours A/B augmente la
densité des mesures, mais pas nécessairement la couverture spatiale. Les
parties blanches de la grille sont non observées et ne doivent pas être
interprétées comme libres. Une carte « complète » de toute la salle ne peut
pas être certifiée avec les seules données disponibles : il faut vérifier les
zones hors champ et refaire des acquisitions à hauteur constante là où des
surfaces restent cachées. Une fermeture de boucle, des références mesurées et
un relevé des murs permettraient une validation plus forte.

\section{Reproduction}
Depuis la racine du dépôt :
\begin{verbatim}
python -m pip install -r tp1/LD06_Atelier/requirements.txt
python tp3/slam.py
python tp3/creer_rapport.py
python -m unittest discover -s tp3 -p "test_*.py" -v
\end{verbatim}
Compiler ensuite \texttt{tp3/rapport/rapport\_tp3.tex} depuis son dossier.
Les CSV, JSON, figures et cartes exportées sont dans \texttt{tp3/resultats/}.
\end{document}
"""

replacements = {
    "@@TOTAL@@": str(DATA["total"]),
    "@@ACCEPTED@@": str(DATA["accepted"]),
    "@@POINTS@@": str(points),
    "@@SEGMENTS@@": str(DATA["vector_segments"]),
    "@@RES@@": f"{DATA['grid_resolution_m']:.2f}".replace(".", ","),
    "@@XMIN@@": f"{extent[0]:.2f}", "@@XMAX@@": f"{extent[1]:.2f}",
    "@@YMIN@@": f"{extent[2]:.2f}", "@@YMAX@@": f"{extent[3]:.2f}",
    "@@ROWS@@": format_rows(),
    "@@REJECTED@@": ", ".join(tex(name) for name in rejected) or "aucun",
}
for key, value in replacements.items():
    template = template.replace(key, value)
(REPORT / "rapport_tp3.tex").write_text(template, encoding="utf-8")
print(f"Rapport TP3 généré : {REPORT / 'rapport_tp3.tex'}")
