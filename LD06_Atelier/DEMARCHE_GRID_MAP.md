# Grid map 2D - demarche du TP

## Lancer et exporter

Double-cliquer Lancer_Grid_Map.bat, ou depuis le dossier projet :

    python LD06_Atelier/viewer.py --grid-map

La grille est reconstruite quand une pose change. Exporter grille sauvegarde
les cellules et les metadonnees courantes. Enregistrer poses reste necessaire
pour conserver les reglages de pose d'une session a l'autre.
Resolution personnalisable : --resolution 0.1 pour des cellules de 10 cm.

    python LD06_Atelier/export_grid_figures.py

Cette commande genere grid_map_finale.png et grid_map_progression.png a partir
des deux scans d'origine et de poses.json, avec une resolution de 5 cm.

## Methode

- Carte ternaire : -1 inconnu, 0 libre, 100 occupe (ces valeurs ne sont pas
  des probabilites). Stockage numpy int16. Etat initial entierement inconnu.
- Emprise calculee sur les points valides transformes et les positions du
  capteur pour tous les scans, avec marge 0.5 m. Resolution 0.05 m par defaut.
- Les CSV contiennent deja les coordonnees cartesiennes en mm ; conversion
  en metres puis rotation et translation : Pglobal = R(theta) Plocal + T.
  Convention Y conservee : dans ces fichiers, Y = -r sin(angle).
- Indices : colonne = floor((x-xmin)/resolution), ligne = floor((y-ymin)/resolution).
  Important pour les coordonnees negatives : floor, et non troncature entiere.
- Filtre : points finis, distance locale de 0.15 a 12 m. Pas de filtrage
  d'intensite ajoute : la qualite n'est pas chargee par le lecteur geometrique.
- Bresenham discretise chaque rayon, du capteur a l'impact inclus.
  Toutes les cellules avant l'impact sont libres, l'impact est occupe.
- Au sein d'un scan : accumulation en ensembles, puis impacts prioritaires.
  Le resultat ne depend donc pas de l'ordre des rayons du meme scan.
- Entre scans : la nouvelle observation remplace l'ancienne dans les cellules
  touchees ; les autres cellules sont conservees. Un ancien obstacle traverse
  par un nouveau rayon peut redevenir libre. Aucun lissage n'est applique.
- Le premier scan cree la carte ; le deuxieme met a jour le meme objet.
  Pour le viewer, on reconstruit depuis les sources a chaque changement de pose,
  afin de ne pas conserver les traces d'une ancienne position du curseur.

## API et fichiers

GridMap(origin, size, resolution) cree une carte vide.
GridMap.update(points_locaux_m, [x_m,y_m,theta_deg]) met a jour une carte existante.
GridMap.load('grid_map.npz') recharge une carte avant une nouvelle mise a jour.

- grid_map.csv : matrice de cellules, separateur point-virgule ; ligne 0 = Y minimum.
- grid_map.json : origine, resolution, dimensions, convention et nombre de scans.
- grid_map.npz : cellules et metadonnees pour rechargement sans perte.
- Images : marron inconnu, vert libre, rouge occupe, positions du capteur en bleu. Echelle identique en X et Y.

## Hypotheses, difficultes et limites

Les scans doivent conserver leur origine capteur (pas seulement des points
fusionnes dont on ne connait plus les positions d'acquisition). Les deux poses
actuelles sont manuellement ajustables et estimees : aucun SLAM ni recalage
automatique n'est ajoute. Une mauvaise pose peut effacer de vrais obstacles.
Seuls les impacts reels sont utilises ; aucune mesure sans retour n'est simulee.
Sur une grille fixe, un impact hors carte est ignore avec son rayon entier ;
le capteur hors carte est rejete. build_grid evite cela en couvrant les scans.
Les intervalles entre faisceaux restent inconnus, surtout a grande distance :
on ne les remplit pas artificiellement. Les vitrages et objets mobiles peuvent
fausser les mesures. Pas de decroissance temporelle ni de confiance probabiliste
pour cette premiere version. L'ordre des scans peut affecter les cellules en conflit.

## Verification

    python -m unittest discover -s LD06_Atelier -p "test_*.py" -v

Tests : rayons horizontaux, verticaux, diagonaux et point unique, indices negatifs,
pose rotation/translation, inconnu/libre/impact, conflits, mise a jour successive,
mesures invalides, limites de carte, resolution, sauvegarde/rechargement.
Les tests des segments de la carte vectorielle sont egalement executes.
