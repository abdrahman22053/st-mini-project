#!/usr/bin/env bash
# Commande unique pour TOUT relancer :   bash run_all.sh
#   1) crée un environnement virtuel figé (.venv) à partir de requirements.txt
#   2) télécharge les données officielles UCI et vérifie leur SHA-256
#   3) exécute le pipeline (diagnostic -> cycles -> train/val/test avec gap -> ablation)
#   4) ré-exécute le notebook de bout en bout (sortie : notebook exécuté en place)
# Option : SKIP_VENV=1 bash run_all.sh  pour utiliser le Python courant.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=42 MPLBACKEND=Agg

if [[ "${SKIP_VENV:-0}" != "1" ]]; then
  PY=$(command -v python3 || command -v python)
  [[ -d .venv ]] || "$PY" -m venv .venv
  # Linux/Mac : .venv/bin ; Windows (Git Bash) : .venv/Scripts
  # shellcheck disable=SC1091
  if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; else source .venv/Scripts/activate; fi
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
fi

python - <<'PY'
import sys
if sys.version_info < (3, 12):
    sys.exit(f"[erreur] Python {sys.version.split()[0]} détecté : installez Python 3.12 ou 3.13 (requirements.txt).")
PY
python src/download_data.py
python src/run_pipeline.py
python -m nbconvert --to notebook --execute --inplace \
       --ExecutePreprocessor.timeout=1200 sujet5_surveillance_compresseur.ipynb
echo "OK : résultats dans results/, figures dans results/figures/, notebook ré-exécuté."
