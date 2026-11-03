"""Régénère le rapport depuis les résultats, sans chiffres figés dans le texte."""
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "resultats"
data = json.loads((OUT / "protocole_et_resultats.json").read_text(encoding="utf-8"))


def read_csv(name):
    with (OUT / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file, delimiter=";"))


def fmt(value, digits=2):
    return "---" if value is None or value == "" else f"{float(value):.{digits}f}".replace(".", ",")


def percent(value):
    return "---" if value is None else f"{fmt(value * 100, 1)}\\,\\%"


LABELS = {
    "grid_multiresolution": "Grille",
    "vector_multiresolution": "Segments",
    "scan_coarse_icp": "Recherche + ICP",
}
summary = data["summary"]
simulation = [item for item in summary if item["dataset"] == "simulation"]
real = [item for item in summary if item["dataset"] == "reel"]
trials = read_csv("essais.csv")
repeatability = read_csv("repetabilite_reelle.csv")


def table(lines):
    return "\n".join(lines)


def latex_name(value):
    return str(value).replace("_", r"\_")


def read_folder_csv(folder, name):
    with (folder / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file, delimiter=";"))


poses = table(
    f"{label.replace('_', ' ')} & {fmt(pose[0], 3)} & {fmt(pose[1], 3)} & {fmt(pose[2], 1)} \\\\"
    for label, pose in data["simulation_poses"].items()
)
offsets = table(
    f"{i} & {fmt(pose[0])} & {fmt(pose[1])} & {fmt(pose[2], 1)} \\\\"
    for i, pose in enumerate(data["initial_offsets"])
)
sim_rows = table(
    f"{LABELS[item['method']]} & {fmt(item['position_error_mean_m'], 3)} & "
    f"{fmt(item['angle_error_mean_deg'], 2)} & {fmt(item['median_seconds'], 3)} & "
    f"{percent(item['success_rate'])} \\\\"
    for item in simulation
)
real_rows = table(
    f"{LABELS[item['method']]} & {fmt(item['median_seconds'], 3)} & "
    f"{fmt(item['mean_residual_rms_capped_m'], 3)} & "
    f"{fmt(item['position_error_mean_m'], 3)} & "
    f"{percent(item['success_rate'])} \\\\"
    for item in real
)
b01_rows = table(
    f"{LABELS[item['method']]} & {fmt(item['estimated_x'], 3)} & "
    f"{fmt(item['estimated_y'], 3)} & {fmt(item['estimated_angle'], 2)} \\\\"
    for item in trials if item["dataset"] == "reel" and item["scan"] == "B_01" and item["trial"] == "0"
)
repeat_rows = table(
    f"{LABELS[item['method']]} & {item['position']} & {fmt(item['mean_x_m'], 3)} & "
    f"{fmt(item['mean_y_m'], 3)} & {fmt(item['std_x_m'], 3)} & "
    f"{fmt(item['std_y_m'], 3)} & {fmt(item['std_angle_deg'], 2)} \\\\"
    for item in repeatability
)

old_scan_rows = []
for position, folder_name in (("A", "position_A_20261103_120212"),
                              ("B", "position_B_20261103_120333")):
    metadata = json.loads((ROOT / "acquisitions" / folder_name / "acquisition.json")
                          .read_text(encoding="utf-8"))
    for name, count in zip(metadata["files"], metadata["point_counts"]):
        role = "référence" if name == "A_01.csv" else "test"
        height = "1,90 m annoncé" if position == "A" else "1,90 m supposé"
        old_scan_rows.append(f"{latex_name(name[:-4])} & {count} & {height} & {role} \\\\")
old_scan_rows = table(old_scan_rows)

build_rows = table(
    f"{dataset.title()} & {LABELS[method]} & "
    f"{fmt(next(float(row['reference_build_seconds']) for row in trials
                 if row['dataset'] == dataset and row['method'] == method), 3)} \\\\"
    for dataset in ("simulation", "reel") for method in LABELS
)

sensitivity_rows = []
for index in range(len(data["initial_offsets"])):
    selected = [row for row in trials if row["dataset"] == "simulation"
                and int(row["trial"]) == index]
    means = [statistics.mean(float(row["position_error_m"]) for row in selected
                             if row["method"] == method) for method in LABELS]
    sensitivity_rows.append(
        f"{index} & {fmt(means[0], 3)} & {fmt(means[1], 3)} & "
        f"{fmt(means[2], 3)} & "
        f"{percent(sum(row['success'] == 'True' for row in selected) / len(selected))} \\\\"
    )
sensitivity_rows = table(sensitivity_rows)

ground_count = len(data["real_ground_truth"]["measurements"])
measured_rows = data["real_ground_truth"]["measurements"]
measurement_table = (
    r"\begin{center}\small\begin{tabular}{lrrrrr}\toprule" "\n"
    r"Scan & $x$ (m) & $y$ (m) & $\theta$ ($^\circ$) & $u_p$ (m) & $u_\theta$ ($^\circ$)\\" "\n"
    r"\midrule" "\n"
    + table(
        f"{label.replace('_', ' ')} & {fmt(item['pose'][0], 3)} & {fmt(item['pose'][1], 3)} & "
        f"{fmt(item['pose'][2], 2)} & {fmt(item['uncertainty_position_m'], 3)} & "
        f"{fmt(item['uncertainty_angle_deg'], 2)} \\\\"
        for label, item in measured_rows.items()
    )
    + "\n\\bottomrule\\end{tabular}\\end{center}"
    if measured_rows else ""
)
ground_text = (
    f"{ground_count} scan(s) ont une pose et des incertitudes mesurées indépendamment. "
    "Seuls ces scans contribuent aux erreurs et aux taux de réussite réels."
    if ground_count else
    "Aucune pose terrain ni incertitude n'a été mesurée indépendamment. "
    "Les erreurs de pose et les taux de réussite réels ne sont pas calculables."
)


def nouveaux_scans_section():
    folder = ROOT / "resultats_nouveaux_scans"
    protocol_file = folder / "protocole_nouveaux_scans.json"
    comparison_file = folder / "comparaison_methodes.csv"
    if not protocol_file.exists() or not comparison_file.exists():
        return ""
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    comparisons = read_folder_csv(folder, "comparaison_methodes.csv")
    quality = read_folder_csv(folder, "qualite_scans.csv")
    pairs = read_folder_csv(folder, "recouvrement_paires.csv")
    if not comparisons:
        return ""
    first_pair = protocol["selected_pairs"][0]
    pair_name = "--".join(first_pair)
    rows = table(
        f"{LABELS[item['method']]} & {fmt(item['initial_angle_deg'], 0)} & "
        f"{fmt(item['estimated_x_m'])} & {fmt(item['estimated_y_m'])} & "
        f"{fmt(item['estimated_angle_deg'])} & "
        f"{fmt(min(float(item['query_20cm']), float(item['reference_20cm'])) * 100, 0)} \\\\"
        for item in comparisons if item["trial"] in {"0", "4"}
    )
    times = table(
        f"{LABELS[method]} & {fmt(statistics.median(float(item['solve_seconds']) for item in comparisons if item['method'] == method), 3)} \\\\"
        for method in LABELS
    )
    quality_rows = table(
        f"{item['scan']} & {item['points_acquired']} & {item['points_compared']} & "
        f"{fmt(item['angular_coverage_deg'], 1)} & "
        f"{'au sol' if item['scan'] == 'N4' else '1,00--1,20 m estimé'} \\\\"
        for item in quality
    )
    pair_rows = table(
        f"{item['reference']}--{item['scan']} & "
        f"{fmt(min(float(item['query_20cm']), float(item['reference_20cm'])) * 100, 0)} & "
        f"{fmt(min(float(item['query_50cm']), float(item['reference_50cm'])) * 100, 0)} & "
        f"{'au sol' if item['same_height'] == 'False' else ('retenue' if item['selected_for_comparison'] == 'True' else 'insuffisant')} \\\\"
        for item in pairs
    )
    detailed_rows = table(
        f"{item['trial']} & {LABELS[item['method']]} & "
        f"({fmt(item['initial_x_m'], 2)};{fmt(item['initial_y_m'], 2)};{fmt(item['initial_angle_deg'], 0)}) & "
        f"{fmt(item['estimated_x_m'], 2)} & {fmt(item['estimated_y_m'], 2)} & "
        f"{fmt(item['estimated_angle_deg'], 2)} & {fmt(item['solve_seconds'], 3)} & "
        f"{fmt(min(float(item['query_20cm']), float(item['reference_20cm'])) * 100, 0)} \\\\"
        for item in comparisons
    )
    section = r"""
\section{Six acquisitions supplémentaires : vérification sur la salle}
Six nouveaux scans LD06, nommés N1 à N6 dans l'ordre des fichiers, ont été
enregistrés dans plusieurs zones de la salle. N1, N2, N3, N5 et N6 ont été
pris à une hauteur estimée entre 1,00 et 1,20 m par l'utilisateur ; cette
hauteur n'a pas été relevée au centimètre. N4 a été pris au sol et est exclu
de la comparaison à hauteur commune. Les six acquisitions sont affichées dans
leurs repères locaux distincts ; les superposer sans estimation de pose serait
géométriquement incorrect.
\begin{center}\small
\begin{tabular}{lrrrl}\toprule
Scan & Points bruts & Points comparés & Couverture ($^\circ$) & Hauteur\\\midrule
@@QUALITYROWS@@
\bottomrule\end{tabular}
\end{center}
Les 153 points comparés environ par scan proviennent du filtrage de portée
puis de l'échantillonnage un point sur trois. La couverture angulaire brute
est proche d'un tour complet ; elle n'implique pas que tous les murs soient
visibles à travers les personnes, meubles et autres occultations.
\begin{figure}[H]\centering
\includegraphics[width=\linewidth]{resultats_nouveaux_scans/six_scans_bruts.png}
\caption{Les six scans bruts. N4 est identifié comme acquisition au sol.}
\end{figure}

Les quinze paires ont été diagnostiquées par recouvrement dans les deux sens.
Le protocole retient une paire à hauteur commune seulement si au moins
40\,\% des points sont à moins de 20 cm et 70\,\% à moins de 50 cm
dans chaque sens après alignement exploratoire. Sur ces données, la seule
paire retenue est \textbf{@@PAIR@@}. Cette sélection utilise le solveur entre
scans et peut le favoriser ; elle ne démontre ni la proximité réelle des
capteurs ni la justesse de la pose estimée. Les quatre autres scans restent
conservés pour les diagnostics et de futurs essais.
\begin{center}\small
\begin{tabular}{lrrl}\toprule
Paire & Min. 20 cm (\%) & Min. 50 cm (\%) & Statut\\\midrule
@@PAIRROWS@@
\bottomrule\end{tabular}
\end{center}
Chaque pourcentage est le minimum des deux fractions : points du scan test
proches de la référence, puis points de la référence proches du scan test.
Un grand recouvrement dans un seul sens peut correspondre à une observation
partielle et ne suffit pas. Les paires contenant N4 sont signalées
\og au sol\fg{} même si un score géométrique paraît favorable.

La paire @@PAIR@@ a été soumise aux trois références avec six départs
strictement identiques : deux départs translatés et les angles initiaux
0, +90, 180 et $-90^\circ$. Extraits pour les départs à 0 et 180 degrés :
\begin{center}\small
\begin{tabular}{lrrrrr}\toprule
Méthode & Départ ($^\circ$) & $\hat x$ (m) & $\hat y$ (m) &
$\hat\theta$ ($^\circ$) & Recouv. 20 cm (\,\%)\\\midrule
@@NEWROWS@@
\bottomrule\end{tabular}
\end{center}
\begin{center}\small
\begin{tabular}{lr}\toprule Méthode & Temps médian par essai (s)\\\midrule
@@NEWTIMES@@
\bottomrule\end{tabular}
\end{center}
Le recouvrement indiqué est le minimum des deux directions et n'est pas une
erreur de position. Les poses estimées varient sensiblement avec le départ ;
le désaccord entre méthodes signale une ambiguïté des structures observées.
Le résidu propre à chaque représentation ne constitue pas une mesure terrain.
\begin{figure}[H]\centering
\includegraphics[width=\linewidth]{resultats_nouveaux_scans/comparaison_paire_selectionnee.png}
\caption{Même paire et même départ de 180 degrés pour les trois méthodes.}
\end{figure}

Les déplacements et rotations réels entre ces acquisitions n'ont pas été
mesurés indépendamment des CSV, pas plus que leurs incertitudes. Il est donc
impossible de calculer l'erreur de position, l'erreur angulaire ou un taux de
réussite réel défendable pour ces essais. Les colonnes correspondantes restent
vides dans le CSV. La simulation ci-dessus est la validation chiffrée avec
poses exactes ; les essais réels évaluent le temps, la cohérence et la
sensibilité à l'initialisation.

\subsection{Tous les essais N2--N5}
Le tableau suivant conserve les 18 combinaisons : six départs identiques
pour chacune des trois méthodes. Les valeurs numériques proviennent
directement du CSV ; les durées peuvent varier d'une exécution à l'autre.
\begin{center}\small\setlength{\tabcolsep}{3pt}
\begin{longtable}{rlrrrrrr}
\toprule Essai & Méthode & Départ $(x;y;\theta)$ & $\hat x$ (m) &
$\hat y$ (m) & $\hat\theta$ ($^\circ$) & Temps (s) & Min. 20 cm (\%)\\\midrule
\endfirsthead
\toprule Essai & Méthode & Départ $(x;y;\theta)$ & $\hat x$ (m) &
$\hat y$ (m) & $\hat\theta$ ($^\circ$) & Temps (s) & Min. 20 cm (\%)\\\midrule
\endhead
@@DETAILEDROWS@@
\bottomrule
\end{longtable}
\end{center}
"""
    return (section.replace("@@PAIR@@", pair_name)
            .replace("@@NEWROWS@@", rows)
            .replace("@@NEWTIMES@@", times)
            .replace("@@QUALITYROWS@@", quality_rows)
            .replace("@@PAIRROWS@@", pair_rows)
            .replace("@@DETAILEDROWS@@", detailed_rows))

report = r"""
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage[margin=2.1cm]{geometry}
\usepackage{amsmath,graphicx,booktabs,float,longtable}
\usepackage[hidelinks]{hyperref}
\graphicspath{{resultats/}}
\hypersetup{pdfauthor={Houssam MAKHLOUK},pdftitle={TP2 - Localisation et Scan Matching}}
\begin{document}
\hypersetup{pageanchor=false}
\begin{titlepage}\centering
\vspace*{1cm}{\Large\bfseries EIGSI LA ROCHELLE\par}
\vspace{.4cm}{\large Année universitaire 2026/2027\par}
\vspace{2cm}{\large RAPPORT DE TRAVAUX PRATIQUES\par}
\vspace{.8cm}\rule{.9\textwidth}{1pt}\par\vspace{.6cm}
{\Huge\bfseries TP -- Jour 2\par}\vspace{.6cm}
{\LARGE Localisation et Scan Matching\par}\vspace{.6cm}
{\large Grille d'occupation, carte vectorielle et scans\par}
\vspace{.6cm}\rule{.9\textwidth}{1pt}
\vfill{\large Réalisé par\par}\vspace{.3cm}
{\LARGE\bfseries Houssam MAKHLOUK\par}
\vspace{.4cm}{\large Étudiant à EIGSI La Rochelle\par}
\vfill{\large 3 novembre 2026\par}
\end{titlepage}
\pagenumbering{roman}\hypersetup{pageanchor=true}
\tableofcontents\clearpage\pagenumbering{arabic}

\section{Objectif et données}
Le TP demande une méthode fonctionnelle par référence et une évaluation chiffrée
sur les mêmes scans et poses initiales. Ici, un scan est localisé par rapport à
une grille d'occupation, à une carte vectorielle et à un scan de référence.
La pose recherchée est $(x,y,\theta)$ dans le plan : $(x,y)$ est exprimé en
mètres et $\theta$ en degrés. Une pose estimée est une sortie d'algorithme ;
elle devient une erreur mesurable seulement si une pose de référence
indépendante est disponible. Le protocole sépare donc explicitement la
simulation, qui dispose de cette référence, des acquisitions réelles.

\subsection{Acquisitions LD06}
Trois scans ont été pris à la position A (457, 519 et 451 points), trois à B
(457, 456 et 456 points). La hauteur annoncée à A est 1,90 m ; elle est
supposée identique à B. La translation, la rotation, la stabilité du montage
et leurs incertitudes n'ont pas été mesurées. A\_01 définit l'origine du repère
et construit seul les trois références. A\_02, A\_03 et B\_01 à B\_03 sont
réservés aux tests.
\begin{center}\small
\begin{tabular}{lrll}\toprule
Scan & Points bruts & Hauteur & Rôle\\\midrule
@@OLDSCANS@@
\bottomrule\end{tabular}
\end{center}
Les acquisitions A et B sont trois tours consécutifs à chacun des deux
emplacements supposés immobiles. La hauteur à A est annoncée à 1,90 m ;
la même hauteur est supposée à B. Cette indication ne donne ni la
translation ni la rotation entre les deux stations. Les six autres
acquisitions du même jour sont décrites séparément en section dédiée,
car leur hauteur n'est pas la même que celle annoncée pour A/B.

\subsection{Simulation à poses exactes}
Une salle asymétrique à décrochement et deux obstacles rectangulaires sont
simulés par lancer de 540 rayons. Les portées subissent un bruit gaussien
indépendant de $\sigma=8$ mm. Les graines sont fixes. Le scan de référence
est à $(0,0,0)$, et les @@NSIM@@ scans de test ont ces poses :
\begin{center}\small
\begin{tabular}{lrrr}\toprule Scan & $x^*$ (m) & $y^*$ (m) & $\theta^*$ ($^\circ$)\\
\midrule
@@POSES@@
\bottomrule\end{tabular}
\end{center}
La vérité terrain sert seulement à fabriquer les départs et calculer les erreurs ;
les solveurs ne la reçoivent pas. Les occultations changent avec la pose.

\section{Méthodes}
Un point du LiDAR de portée $r$ et d'angle $\alpha$ est converti en
$p_l=(r\cos\alpha,r\sin\alpha)$. La pose $q=(x,y,\theta)$ le transforme par
\[
p_g=R(\theta)p_l+\begin{bmatrix}x\\y\end{bmatrix},\qquad
R(\theta)=\begin{bmatrix}\cos\theta&-\sin\theta\\
\sin\theta&\cos\theta\end{bmatrix}.
\]
Le filtre conserve les mesures de portée entre 0,15 et 12 m ; un point
sur trois est ensuite donné aux trois solveurs. La même convention de
repère et le même scan test sont employés pour chaque comparaison.
Chaque support de référence est construit avec le \emph{scan de référence
seul} : les scans de test ne participent pas à sa construction.
\begin{center}\small
\begin{tabular}{lp{4.0cm}p{5.2cm}}\toprule
Référence & Représentation & Distance évaluée pour un impact test\\\midrule
Grid map & Cellules libres, occupées et non observées & Centre de cellule occupée la plus proche\\
Carte vectorielle & Segments extraits des impacts & Point au segment le plus proche\\
Scan & Points 2D du tour de référence & Point du scan de référence le plus proche\\
\bottomrule\end{tabular}
\end{center}

\subsection{Grille d'occupation}
A\_01 produit une grille ternaire de résolution 6 cm : libre sur le rayon,
occupé au point d'impact, inconnu ailleurs. Un champ pré-calculé donne la
distance au centre de la cellule occupée la plus proche. Hors carte, le résidu
est 1 m avant plafonnement. Ce score ne vérifie pas les rayons libres du scan test.
La grille est une référence construite par tracé des faisceaux. Une cellule
non observée n'est pas déclarée libre. Le score ne pénalise cependant pas
directement un impact qui contredirait un ancien rayon libre ; des obstacles
mobiles et des occultations peuvent tromper l'appariement.

\subsection{Carte vectorielle}
A\_01 est regroupé par continuité et ajusté en segments. Seuils : 35 cm entre
voisins, erreur de droite 4,5 cm, au moins cinq points et longueur de 15 cm.
Pour chaque point et segment $[a,b]$, la distance est
\[
d(p,[a,b])=\|p-a-t(b-a)\|,\quad
t=\operatorname{clip}\left(\frac{(p-a)\cdot(b-a)}{\|b-a\|^2},0,1\right).
\]
Le résidu est le minimum sur les segments de référence.
Le regroupement utilise l'ordre angulaire des points et sépare les ruptures
de continuité. Un mur mal échantillonné peut se morceler en plusieurs
segments ; un meuble proche peut être confondu avec une portion de mur.
La carte vectorielle est construite à partir du même A\_01 que la grille,
sans utiliser les scans de test pour améliorer les segments.

\subsection{Recherche hiérarchique}
Sur les deux cartes, le coût est
$J(q)=N^{-1}\sum_i\min(d(T_qp_i),0{,}6)^2$.
Le premier niveau teste $\pm2{,}5$ m selon X et Y et $\pm100^\circ$
autour de la pose initiale, par pas de 0,5 m et $10^\circ$. Son classement
rapide utilise un tiers du nuage de test déjà sous-échantillonné. Les 120
meilleurs candidats sont réévalués sur tous les points et huit hypothèses
distinctes sont retenues. Trois niveaux les affinent dans un voisinage de
$\pm2$ pas : $(0{,}15\,\mathrm m,3^\circ)$,
$(0{,}04\,\mathrm m,1^\circ)$ et $(0{,}01\,\mathrm m,0{,}25^\circ)$.
La portée théorique cumulée est $\pm2{,}90$ m et $\pm108{,}5^\circ$.

\subsection{Localisation entre scans}
La même recherche utilise les distances au plus proche point de A\_01. Elle
initialise un ICP point-à-point. L'ICP garde les 85\,\% de paires les plus
proches, ajuste une pose rigide par SVD et compose les poses (70 itérations
au plus). La pose avant ou après ICP ayant le meilleur score est retenue.
Le temps de ce solveur comprend recherche et ICP.
L'ICP est local : si l'initialisation fournit des correspondances sur le
mauvais mur, il peut converger vers une pose plausible mais fausse.
La recherche initiale élargit son domaine de convergence sans garantir
l'unicité du résultat dans une salle symétrique.

\section{Protocole}
L'erreur est $e_p=\|\hat t-t^*\|$ en position et
$e_\theta=|\operatorname{wrap}(\hat\theta-\theta^*)|$ en angle.
La réussite exige $e_p\leq0{,}20$ m \emph{et} $e_\theta\leq5^\circ$.
Les perturbations appliquées à chaque pose simulée sont :
\begin{center}\small
\begin{tabular}{rrrr}\toprule Essai & $\Delta x$ (m) & $\Delta y$ (m) & $\Delta\theta$ ($^\circ$)\\
\midrule
@@OFFSETS@@
\bottomrule\end{tabular}
\end{center}
Les mêmes scans et départs sont fournis aux trois méthodes à chaque essai.
En réel, les cinq premiers écarts partent de $(0,0,0)$.
@@NSIM@@ scans simulés $\times10$ départs $\times3$ méthodes donnent
@@SIMTRIALS@@ essais ; cinq scans réels $\times5\times3$ donnent
@@REALTRIALS@@ essais. Les temps sont mesurés hors construction des références ;
le temps de préparation figure séparément dans le CSV détaillé.
Le chronomètre entoure le solveur pour chaque essai. Les temps de
construction des références, calculés une fois par méthode et jeu de
données, sont :
\begin{center}\small
\begin{tabular}{llr}\toprule Jeu & Méthode & Préparation (s)\\\midrule
@@BUILDTIMES@@
\bottomrule\end{tabular}
\end{center}
Le calcul de l'erreur utilise la norme euclidienne de la translation et la
différence d'angles ramenée dans $[-180^\circ,180^\circ)$. Le succès exige
\emph{simultanément} les deux seuils ; un faible résidu géométrique n'entre
pas dans cette définition.

\section{Résultats en simulation}
\begin{table}[H]\centering\small
\begin{tabular}{lrrrr}\toprule Méthode & $e_p$ moyen (m) & $e_\theta$ moyen ($^\circ$) &
Temps médian (s) & Réussite\\\midrule
@@SIMTABLE@@
\bottomrule\end{tabular}
\caption{@@PERMETHOD@@ essais par méthode, échecs inclus.}
\end{table}
Ces taux proviennent d'un seul environnement simulé et ne garantissent pas
la même performance dans une autre salle.
Les 60 essais par méthode comprennent les dix perturbations ci-dessus
sur chacun des six scans ; les échecs éventuels ne sont pas retirés de la
moyenne. Le tableau suivant donne l'erreur de position moyenne sur les
six scans à chaque départ, et le taux de réussite commun aux trois méthodes.
\begin{center}\small
\begin{tabular}{rrrrr}\toprule
Départ & Grille (m) & Segments (m) & Scan + ICP (m) & Réussite\\\midrule
@@SENSITIVITY@@
\bottomrule\end{tabular}
\end{center}
Les dix perturbations testées sont corrigées dans la scène simulée choisie.
Cela mesure la sensibilité dans cet intervalle seulement ; au-delà des
départs testés et dans une autre géométrie, le taux peut diminuer.
\begin{figure}[H]\centering
\includegraphics[width=\linewidth]{comparaison_simulation.png}
\caption{Erreurs de position, d'orientation et temps, échecs inclus.}
\end{figure}
\begin{figure}[H]\centering
\includegraphics[width=.94\linewidth]{sensibilite_initialisation.png}
\caption{Réussite pour chaque perturbation, sur @@NSIM@@ scans.}
\end{figure}
\begin{figure}[H]\centering
\includegraphics[width=\linewidth]{simulation_localisation.png}
\caption{Exemple des trois méthodes depuis le même départ.}
\end{figure}

\section{Résultats sur les acquisitions réelles}
Les trois références sont construites sur A\_01 et les cinq autres tours
A/B servent de tests. Pour A\_02 et A\_03, une pose proche de l'origine
est plausible si le capteur est effectivement resté immobile. Pour les
scans B, la pose physique n'a pas été relevée. Les valeurs suivantes
décrivent donc la vitesse et la cohérence interne, sans fournir une
erreur absolue sur le robot.
\begin{table}[H]\centering\small
\begin{tabular}{lrrrr}\toprule Méthode & Temps médian (s) & Résidu (m) &
$e_p$ moyen (m) & Réussite\\\midrule
@@REALTABLE@@
\bottomrule\end{tabular}
\caption{@@REALPERMETHOD@@ essais par méthode. --- signifie absence de vérité
terrain. Les résidus des trois représentations ne sont pas directement comparables.}
\end{table}
@@GROUNDTEXT@@ Les mesures et leurs incertitudes peuvent être saisies dans
\texttt{references\_mesurees.csv}, puis le même script recalcule les erreurs.
@@MEASUREDTABLE@@
Depuis le départ nul, les poses estimées de B\_01 sont :
\begin{center}\small
\begin{tabular}{lrrr}\toprule Méthode & $x$ (m) & $y$ (m) & $\theta$ ($^\circ$)\\
\midrule
@@B01TABLE@@
\bottomrule\end{tabular}
\end{center}
Il s'agit d'estimations des algorithmes, pas de mesures physiques.
La répétabilité entre acquisitions du même emplacement supposé est :
\begin{center}\small
\begin{tabular}{llrrrrr}\toprule
Méthode & Position & $\bar x$ & $\bar y$ & $s_x$ & $s_y$ & $s_\theta$\\\midrule
@@REPEATTABLE@@
\bottomrule\end{tabular}
\end{center}
Moyennes et écarts types X/Y sont en mètres ; $s_\theta$ est en degrés.
A contient deux scans de test et B en contient trois. Cette dispersion ne
remplace pas l'incertitude d'une mesure terrain indépendante.
Un faible écart type peut se produire si le solveur reproduit toujours le
même mauvais appariement ; il n'est pas une preuve de justesse.
\begin{figure}[H]\centering
\includegraphics[width=\linewidth]{localisation_reelle.png}
\caption{A\_02 et B\_01 localisés sur A\_01.}
\end{figure}

@@NEWSCANS@@

\section{Réponse aux exigences du TP}
\begin{enumerate}
\item \textbf{Localisation sur grid map :} construction de la carte avec un
seul scan de référence, puis recherche de pose minimisant la distance
des impacts aux cellules occupées. Les résultats simulés et réels sont
présentés ci-dessus.
\item \textbf{Localisation sur carte vectorielle :} segments extraits de la
même référence, puis recherche de pose par distance point--segment.
\item \textbf{Localisation entre scans :} recherche de pose par distance
point--point, suivie d'un ICP.
\item \textbf{Comparaison équitable :} les trois méthodes reçoivent les
mêmes scans filtrés et les mêmes départs. Leurs références sont
construites indépendamment des scans tests.
\item \textbf{Évaluation chiffrée :} les poses exactes de simulation
permettent de calculer les erreurs de position et d'angle, le temps,
et le taux de réussite selon 0,20 m et 5 degrés. Les départs sont
variés selon les tableaux précédents.
\item \textbf{Incertitude terrain :} aucune pose robot n'a été relevée
avec un instrument externe ; aucune incertitude de cette mesure
n'est donc disponible. Les CSV réels permettent un diagnostic de
cohérence, pas une erreur métrique vérifiée sur robot.
\end{enumerate}
Pour compléter la dernière exigence sur le robot, il faut mesurer dans
le repère de la salle les poses $(x,y,\theta)$ de chaque prise, documenter
la précision du mètre et du rapporteur utilisés, puis relancer
\texttt{evaluer.py} avec \texttt{references\_mesurees.csv}. Ces valeurs ne
peuvent pas être déduites comme vérité terrain de l'algorithme évalué.

\section{Vérification et limites}
Les tests couvrent les distances, le raycasting, les poses connues, les grandes
erreurs initiales et les références terrain partielles.
\begin{verbatim}
python tp2/evaluer.py
python tp2/evaluer_nouveaux_scans.py
python tp2/creer_rapport.py
python -m unittest discover -s tp2 -p "test_*.py" -v
\end{verbatim}
Les CSV, figures et paramètres sont dans \texttt{tp2/resultats} et
\texttt{tp2/resultats\_nouveaux\_scans}. Les codes sont dans
\texttt{tp2/localisation.py}, \texttt{tp2/evaluer.py} et
\texttt{tp2/evaluer\_nouveaux\_scans.py}. Les temps
dépendent de la machine. Le faible nombre de scènes simulées, les occultations,
le sous-échantillonnage, la carte d'un seul tour et les symétries limitent
les conclusions. Les trois types de référence sont implémentés et comparés.
La validation métrique sur robot nécessite encore des poses et incertitudes
relevées indépendamment des scans.
\end{document}
"""

for marker, value in {
    "@@NSIM@@": str(len(data["simulation_poses"])),
    "@@POSES@@": poses,
    "@@OFFSETS@@": offsets,
    "@@SIMTRIALS@@": str(sum(item["trials"] for item in simulation)),
    "@@REALTRIALS@@": str(sum(item["trials"] for item in real)),
    "@@PERMETHOD@@": str(simulation[0]["trials"]),
    "@@REALPERMETHOD@@": str(real[0]["trials"]),
    "@@SIMTABLE@@": sim_rows,
    "@@REALTABLE@@": real_rows,
    "@@GROUNDTEXT@@": ground_text,
    "@@MEASUREDTABLE@@": measurement_table,
    "@@B01TABLE@@": b01_rows,
    "@@REPEATTABLE@@": repeat_rows,
    "@@OLDSCANS@@": old_scan_rows,
    "@@BUILDTIMES@@": build_rows,
    "@@SENSITIVITY@@": sensitivity_rows,
    "@@NEWSCANS@@": nouveaux_scans_section(),
}.items():
    report = report.replace(marker, value)
(ROOT / "rapport_tp2.tex").write_text(report, encoding="utf-8")
print("Rapport TP2 généré depuis les résultats calculés.")
