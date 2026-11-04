# Atelier LiDAR CSV

Ouvrir `index.html` directement dans un navigateur. Glisser plusieurs CSV LD06 dans la zone d'import. Les points sont affichés en vue de dessus ; le premier scan fixe le repère, les autres sont alignés automatiquement puis peuvent être corrigés avec X, Y et la rotation. Exporter le plan en PNG, les points fusionnés et les poses en CSV.

Formats acceptés : CSV séparé par virgule ou point-virgule, décimales avec point ou virgule, colonnes `x_lib_mm`/`y_lib_mm` ou `angle_deg`/`dist_mm`. Les coordonnées X/Y du capteur sont prioritaires sur les valeurs polaires. Les fichiers ne quittent pas le navigateur.

L'alignement est une estimation géométrique : des scans sans murs communs, pris à des hauteurs différentes ou dans une salle symétrique peuvent s'aligner incorrectement. Vérifier les correspondances et ajuster les poses manuellement avant d'utiliser les exports. Les poses ne sont pas des références mesurées pour le TP2.
