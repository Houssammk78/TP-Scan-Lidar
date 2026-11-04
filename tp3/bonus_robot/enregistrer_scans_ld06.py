#!/usr/bin/env python3
"""Enregistre les scans binaires du LD06 sur le point d'acces Wi-Fi ESP32.

Compatible avec ESP32_Robot_Rotation_Gauche_Droite_LD06_V2.ino :
  8 octets : pose X (int16), pose Y (int16), pose angle (uint16)
             et nombre de points (uint16), en little-endian.
  Chaque point : angle en centidegres (uint16), distance en mm
                 (uint16), intensite (uint8).

Python 3, bibliotheque standard uniquement.
"""
from __future__ import annotations

import csv
import json
import math
import struct
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://192.168.4.1"
DOSSIER = Path(__file__).resolve().parent / "scans_ld06"
DELAI_RESEAU = 5
INTERVALLE_AUTO = 1.0
NB_AUTO = 10
ENTETES = ["point_index", "angle_deg", "dist_mm", "intensity", "x_lib_mm", "y_lib_mm"]
ENTETES_TOTAL = ["scan_id", "horodatage_pc", *ENTETES, "pose_x", "pose_y", "pose_angle_deg"]


def recuperer(chemin: str) -> bytes:
    req = Request(BASE + chemin, headers={"Cache-Control": "no-cache"})
    with urlopen(req, timeout=DELAI_RESEAU) as response:
        return response.read()


def verifier_lidar() -> dict:
    statut = json.loads(recuperer("/lidar_status"))
    if not statut.get("enabled", False):
        raise RuntimeError("LiDAR desactive dans l'ESP32 : ACTIVER_LIDAR doit valoir 1.")
    nb = int(statut.get("points", 0))
    age = int(statut.get("age_ms", -1))
    if nb <= 0 or age < 0:
        raise RuntimeError("Aucun scan valide : verifier alimentation et broches RX33/PWM32.")
    if age > 5000:
        raise RuntimeError(f"Scan trop ancien ({age} ms). Verifier que le LiDAR tourne.")
    print(f"LiDAR OK : {nb} points, age du dernier scan : {age} ms")
    return statut


def decoder_scan(b: bytes):
    if len(b) < 8:
        raise ValueError(f"Reponse trop courte ({len(b)} octets).")
    pose_x, pose_y, pose_angle, n = struct.unpack_from("<hhHH", b, 0)
    if not (1 <= n <= 460):
        raise ValueError(f"Nombre de points inattendu : {n}")
    attendu = 8 + 5*n
    if len(b) != attendu:
        raise ValueError(f"Taille invalide : {len(b)} octets, attendu {attendu}.")
    lignes = []
    for i in range(n):
        angle_cdeg, dist_mm, intensite = struct.unpack_from("<HHB", b, 8 + 5*i)
        angle = angle_cdeg / 100.0
        radians = math.radians(angle)
        # Convention des anciens CSV LD06 de ce projet : Y croissant vers le bas.
        x = int(dist_mm * math.cos(radians))
        y = int(-dist_mm * math.sin(radians))
        lignes.append([i, f"{angle:.2f}", dist_mm, intensite, x, y])
    return (pose_x, pose_y, pose_angle / 100.0), lignes


def sauver_un_scan(scan_id: int, fichier_total):
    # Le firmware interrompt les nouvelles lectures pendant le mouvement :
    # effectuer les captures robot arrete pour eviter les mesures anciennes.
    verifier_lidar()
    donnees = recuperer("/scan")
    pose, lignes = decoder_scan(donnees)
    horodatage = datetime.now().astimezone()
    nom = f"scan_{horodatage.strftime('%Y%m%d_%H%M%S_%f')}.csv"
    chemin = DOSSIER / nom
    with chemin.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(ENTETES)
        writer.writerows(lignes)

    for ligne in lignes:
        fichier_total.writerow([scan_id, horodatage.isoformat(timespec="milliseconds"), *ligne, *pose])
    print(f"Scan {scan_id} : {len(lignes)} points -> {chemin.name}")
    return chemin


def main():
    print("=== Acquisition CSV - LiDAR LD06 / ESP32 ===")
    print(f"Connexion ESP32 : {BASE}")
    print("Arreter le robot et garder le LiDAR alimente pendant les captures.")
    DOSSIER.mkdir(parents=True, exist_ok=True)
    try:
        verifier_lidar()
    except Exception as exc:
        print(f"ERREUR : {exc}")
        print("Verifier le Wi-Fi RobotESP32, puis ouvrir http://192.168.4.1/lidar_status")
        return

    total = DOSSIER / f"tous_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    numero = 0
    with total.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(ENTETES_TOTAL)
        print("\nENTREE = enregistrer un scan ; A = 10 scans (1/s) ; Q = quitter")
        while True:
            try:
                commande = input("Commande : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break
            if commande == "q":
                break
            nb = NB_AUTO if commande == "a" else 1
            if commande not in ("", "a"):
                print("Commande inconnue. Appuyer sur Entree, A ou Q.")
                continue
            for i in range(nb):
                try:
                    numero += 1
                    sauver_un_scan(numero, writer)
                    f.flush()
                except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
                    numero -= 1
                    print(f"ERREUR acquisition : {exc}")
                    print("Verifier le lien Wi-Fi et l'etat du LiDAR.")
                    break
                if i + 1 < nb:
                    time.sleep(INTERVALLE_AUTO)
    print(f"\nTermine : {numero} scan(s) sauvegarde(s).")
    print(f"CSV individuels et groupe : {DOSSIER}")
    if numero == 0:
        # Nettoyage d'un CSV total vide.
        total.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
