"""Télécharge le jeu de données officiel UCI MetroPT-3 et vérifie son empreinte SHA-256.

    python src/download_data.py

Robuste aux coupures réseau : le téléchargement reprend là où il s'est arrêté
(en-tête HTTP Range), avec plusieurs tentatives. Si tout échoue, télécharger le
zip à la main (URL ci-dessous) et le placer dans data/ sous le nom metropt3.zip.
"""
from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
CSV_NAME = "MetroPT3(AirCompressor).csv"
CSV_SHA256 = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
ZIP_SIZE = 218_381_995
DATA = Path(__file__).resolve().parents[1] / "data"
MAX_TRIES = 30


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(zpath: Path) -> None:
    for attempt in range(1, MAX_TRIES + 1):
        done = zpath.stat().st_size if zpath.exists() else 0
        if done >= ZIP_SIZE:
            return
        req = urllib.request.Request(URL, headers={"Range": f"bytes={done}-"} if done else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                mode = "ab" if (done and r.status == 206) else "wb"   # 206 = reprise acceptée
                with open(zpath, mode) as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                        print(f"\r  {zpath.stat().st_size / 1e6:6.1f} / {ZIP_SIZE / 1e6:.1f} Mo", end="", flush=True)
        except (OSError, urllib.error.URLError, ConnectionError) as e:   # IncompleteRead, timeout, reset...
            print(f"\n  coupure réseau ({type(e).__name__}), tentative {attempt}/{MAX_TRIES} : reprise dans 5 s")
            time.sleep(5)
    if not zpath.exists() or zpath.stat().st_size < ZIP_SIZE:
        sys.exit(f"[erreur] téléchargement incomplet. Téléchargez {URL} à la main, "
                 f"placez-le dans {DATA} sous le nom metropt3.zip, puis relancez.")


def main() -> None:
    DATA.mkdir(exist_ok=True)
    csv = DATA / CSV_NAME
    if csv.exists() and sha256(csv) == CSV_SHA256:
        print(f"[ok] {CSV_NAME} déjà présent et vérifié (SHA-256).")
        return
    zpath = DATA / "metropt3.zip"
    print(f"Téléchargement de {URL} (~220 Mo, reprise automatique en cas de coupure)...")
    download(zpath)
    print()
    with zipfile.ZipFile(zpath) as z:
        z.extract(CSV_NAME, DATA)
    digest = sha256(csv)
    if digest != CSV_SHA256:
        zpath.unlink()
        sys.exit(f"[erreur] SHA-256 inattendu ({digest}) : zip supprimé, relancez.")
    zpath.unlink()
    print(f"[ok] {csv} téléchargé et vérifié.")


if __name__ == "__main__":
    main()
