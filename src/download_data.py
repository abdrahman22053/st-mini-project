"""Télécharge le jeu de données officiel UCI MetroPT-3 et vérifie son empreinte SHA-256.

    python src/download_data.py
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
CSV_NAME = "MetroPT3(AirCompressor).csv"
CSV_SHA256 = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
DATA = Path(__file__).resolve().parents[1] / "data"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    DATA.mkdir(exist_ok=True)
    csv = DATA / CSV_NAME
    if csv.exists() and sha256(csv) == CSV_SHA256:
        print(f"[ok] {csv.name} déjà présent et vérifié (SHA-256).")
        return
    zpath = DATA / "metropt3.zip"
    print(f"Téléchargement de {URL} (~220 Mo)...")
    with urllib.request.urlopen(URL) as r, open(zpath, "wb") as f:
        shutil.copyfileobj(r, f)
    with zipfile.ZipFile(zpath) as z:
        z.extract(CSV_NAME, DATA)
    zpath.unlink()
    digest = sha256(csv)
    if digest != CSV_SHA256:
        sys.exit(f"[erreur] SHA-256 inattendu : {digest}")
    print(f"[ok] {csv} téléchargé et vérifié.")


if __name__ == "__main__":
    main()
