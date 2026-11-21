"""Pipeline complet et reproductible du Sujet 5 (MetroPT-3).

    python src/run_pipeline.py            (appelé par run_all.sh)

Étapes : chargement -> diagnostic -> cycles causaux -> découpage chronologique
avec gap -> ajustement sur TRAIN -> choix (quantile, persistance) sur VALIDATION
-> évaluation UNIQUE sur TEST -> ablation -> figures + résultats JSON/CSV.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detectors import (FEATURE_GROUPS, ALL_FEATURES, SEED, IForestDetector,  # noqa: E402
                       PCADetector, ResidualBaseline, add_context, persist)
from evaluation import FAILURES, evaluate  # noqa: E402
from features import build_cycles, diagnose_grid, load_raw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "MetroPT3(AirCompressor).csv"
OUT = ROOT / "results"
FIG = OUT / "figures"

# ------------------------------------------------------------------ découpage
# Dates de coupure fixées AVANT de regarder les performances. Le gap (3 jours)
# dépasse la mémoire maximale des indicateurs (15 cycles ~ 8 h, EWMA span 10,
# persistance <= 6 cycles) : aucun cycle de validation/test ne « voit » le train.
SPLITS = {
    "train": ("2020-02-01", "2020-03-31 23:59:59"),   # aucune panne signalée
    "val":   ("2020-04-04", "2020-05-10 23:59:59"),   # contient la panne #1
    "test":  ("2020-05-14", "2020-09-01 23:59:59"),   # pannes #2, #3, #4 (utilisé une seule fois)
}
GAP_DAYS = 3
WINDOW_DAYS = 7          # fenêtre utile pour l'atelier (planifier une rentrée au dépôt)
FA_BUDGET = 2.0          # fausses alertes / mois tolérées lors du choix sur validation
QUANTILES = [0.95, 0.98, 0.99, 0.995, 0.999]
PERSISTENCES = [1, 3, 6]


def set_seeds():
    random.seed(SEED)
    np.random.seed(SEED)
    os.environ["PYTHONHASHSEED"] = str(SEED)


def split_mask(cyc, name):
    a, b = SPLITS[name]
    return cyc["decision_time"].between(pd.Timestamp(a), pd.Timestamp(b))


def alarms_for(scores, thr, k):
    return persist(scores > thr, k)


def tune(name, scores, train_scores, cyc, val_m, log):
    """Grille (quantile du score d'entraînement, persistance) choisie sur VALIDATION :
    1) respecter le budget FA/mois, 2) maximiser le rappel par événement,
    3) à égalité, prendre le réglage le PLUS SENSIBLE (quantile bas, persistance courte),
    car une panne en ligne coûte ~100 fois plus qu'une fausse alerte (cf. rapport)."""
    grid = []
    for q, k in itertools.product(QUANTILES, PERSISTENCES):
        thr = float(np.nanquantile(train_scores, q))
        ev = evaluate(cyc, alarms_for(scores, thr, k) & val_m, SPLITS["val"], WINDOW_DAYS)
        grid.append({"detecteur": name, "quantile": q, "persistance": k, "seuil": thr,
                     "rappel_val": ev["n_detectees_avant"], "FA_mois_val": ev["FA_par_mois"]})
    g = pd.DataFrame(grid)
    ok = g[g["FA_mois_val"] <= FA_BUDGET]
    pool = ok if len(ok) else g
    best = pool.sort_values(["rappel_val", "quantile", "persistance"],
                            ascending=[False, True, True]).iloc[0]
    log.info("[%s] choix sur validation : q=%.3f, K=%d, seuil=%.4f (rappel_val=%d, FA/mois_val=%.2f)",
             name, best["quantile"], best["persistance"], best["seuil"], best["rappel_val"], best["FA_mois_val"])
    return best, g


def main():
    set_seeds()
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(OUT / "pipeline.log", mode="w"),
                                  logging.StreamHandler()])
    log = logging.getLogger("pipeline")
    if not DATA.exists():
        sys.exit(f"Données absentes : {DATA}. Lancer d'abord : python src/download_data.py")

    # 1. Diagnostic --------------------------------------------------------
    df = load_raw(DATA)
    diag = diagnose_grid(df)
    log.info("Diagnostic grille : %s", diag)

    # 2. Cycles + contexte --------------------------------------------------
    cyc = add_context(build_cycles(df))
    m = {s: split_mask(cyc, s) for s in SPLITS}
    for s in SPLITS:
        log.info("Split %-5s %s -> %s : %d cycles", s, *SPLITS[s], int(m[s].sum()))
    # vérifications anti-fuite
    assert cyc.loc[m["train"], "decision_time"].max() + pd.Timedelta(days=GAP_DAYS) <= cyc.loc[m["val"], "decision_time"].min()
    assert cyc.loc[m["val"], "decision_time"].max() + pd.Timedelta(days=GAP_DAYS) <= cyc.loc[m["test"], "decision_time"].min()
    # Nettoyage de la période normale (calculé sur le TRAIN seulement) : on retire de
    # la référence les journées dont la chute de pression médiane au repos est
    # aberrante (> médiane + 3 MAD des journées d'entraînement).
    tr = cyc[m["train"]]
    daily = tr.groupby(tr["decision_time"].dt.normalize())["leak_rate"].median()
    med, mad = daily.median(), (daily - daily.median()).abs().median() * 1.4826
    bad_days = daily[daily > med + 3 * mad].index
    keep = ~tr["decision_time"].dt.normalize().isin(bad_days)
    train = tr[keep]
    log.info("Période normale : %d jours suspects exclus de la référence (%s) -> %d cycles de référence",
             len(bad_days), ", ".join(d.strftime("%d/%m") for d in bad_days), len(train))

    # 3. Détecteurs ajustés sur TRAIN uniquement ----------------------------
    dets = {
        "Baseline (résidu Ridge + EWMA)": ResidualBaseline().fit(train),
        "Isolation Forest": IForestDetector().fit(train),
        "ACP (T² / SPE)": PCADetector().fit(train),
    }
    rows, grids, chosen = [], [], {}
    for name, det in dets.items():
        scores = det.score(cyc)
        cyc[f"score::{name}"] = scores
        best, g = tune(name, scores, det.train_scores, cyc, m["val"], log)
        grids.append(g)
        alarm = alarms_for(scores, best["seuil"], int(best["persistance"]))
        cyc[f"alarm::{name}"] = alarm
        chosen[name] = {"quantile": float(best["quantile"]), "persistance": int(best["persistance"]),
                        "seuil": float(best["seuil"])}
        for split in ["val", "test"]:
            ev = evaluate(cyc, alarm & m[split], SPLITS[split], WINDOW_DAYS)
            rows.append({"detecteur": name, "split": split, **ev})
            log.info("[%s] %s : %s", name, split, {k: ev[k] for k in
                     ["n_detectees_avant", "n_pannes", "FA_par_mois", "FA_par_mois_IC95"]})

    # 4. Sensibilité à la fenêtre d'anticipation (test, configuration figée) --
    sens = []
    for name in dets:
        for w in [1, 3, 5, 7, 14]:
            ev = evaluate(cyc, cyc[f"alarm::{name}"] & m["test"], SPLITS["test"], w)
            sens.append({"detecteur": name, "fenetre_j": w, "detectees": ev["n_detectees_avant"],
                         "n_pannes": ev["n_pannes"], "FA_par_mois": ev["FA_par_mois"],
                         "rappel_aleatoire": ev["rappel_detecteur_aleatoire"]})

    # 5. Ablation (Isolation Forest) : on retire un groupe de capteurs à la fois -
    abl = []
    variants = {"complet": ALL_FEATURES}
    variants |= {f"sans {g}": [c for c in ALL_FEATURES if c not in cols] for g, cols in FEATURE_GROUPS.items()}
    variants["seulement repos_fuite"] = FEATURE_GROUPS["repos_fuite"]
    for vname, feats in variants.items():
        det = IForestDetector(features=feats).fit(train)
        s = det.score(cyc)
        best, _ = tune(f"IF {vname}", s, det.train_scores, cyc, m["val"], log)
        a = alarms_for(s, best["seuil"], int(best["persistance"]))
        ev_v = evaluate(cyc, a & m["val"], SPLITS["val"], WINDOW_DAYS)
        ev_t = evaluate(cyc, a & m["test"], SPLITS["test"], WINDOW_DAYS)
        abl.append({"variante": vname, "n_variables": len(feats),
                    "q": best["quantile"], "K": int(best["persistance"]),
                    "val_detectees": ev_v["n_detectees_avant"], "val_FA_mois": ev_v["FA_par_mois"],
                    "test_detectees": ev_t["n_detectees_avant"], "test_FA_mois": ev_t["FA_par_mois"],
                    "test_avances_h": [p["avance_h"] for p in ev_t["pannes"]]})

    # 5bis. Coût d'exploitation sur le TEST (hypothèses de coûts : voir rapport §6)
    C_FA, C_TP, C_FN = 150.0, 200.0, 20000.0
    couts = []
    test_fail = sum(1 for r in rows if r["split"] == "test" for _ in r["pannes"]) // len(dets)
    couts.append({"strategie": "Aucune surveillance (maintenance corrective)", "FA": 0, "pannes_ratees": test_fail,
                  "cout_total_EUR": test_fail * C_FN})
    for r in rows:
        if r["split"] != "test":
            continue
        k, n = r["n_detectees_avant"], r["n_pannes"]
        couts.append({"strategie": r["detecteur"], "FA": r["fausses_alertes"], "pannes_ratees": n - k,
                      "cout_total_EUR": r["fausses_alertes"] * C_FA + k * C_TP + (n - k) * C_FN})
    pd.DataFrame(couts).to_csv(OUT / "couts_test.csv", index=False)

    # 6. Sauvegardes ----------------------------------------------------------
    flat = pd.DataFrame([{k: v for k, v in r.items() if k != "pannes"} for r in rows])
    flat.to_csv(OUT / "metriques_par_split.csv", index=False)
    pannes = pd.DataFrame([{"detecteur": r["detecteur"], "split": r["split"], **p}
                           for r in rows for p in r["pannes"]])
    pannes.to_csv(OUT / "detection_par_panne.csv", index=False)
    pd.concat(grids).to_csv(OUT / "grille_validation.csv", index=False)
    pd.DataFrame(sens).to_csv(OUT / "sensibilite_fenetre.csv", index=False)
    pd.DataFrame(abl).to_csv(OUT / "ablation.csv", index=False)
    with open(OUT / "resultats.json", "w") as f:
        json.dump({"diagnostic": diag, "jours_exclus_reference": [str(d.date()) for d in bad_days], "splits": SPLITS, "gap_jours": GAP_DAYS,
                   "fenetre_anticipation_j": WINDOW_DAYS, "budget_FA_mois_validation": FA_BUDGET,
                   "configuration_choisie_sur_validation": chosen, "resultats": rows,
                   "n_cycles": int(len(cyc))}, f, indent=2, ensure_ascii=False, default=str)
    cyc.drop(columns=[c for c in cyc.columns if c.startswith("alarm::")]).to_csv(OUT / "cycles_scores.csv.gz", index=False)

    import figures
    figures.make_all(df, cyc, dets, chosen, SPLITS, FAILURES, FIG)
    log.info("Terminé. Résultats dans %s", OUT)
    pd.set_option("display.width", 250)
    print(flat[["detecteur", "split", "n_pannes", "n_detectees_avant", "FA_par_mois", "FA_par_mois_IC95"]].to_string())
    print(pannes.to_string())
    print(pd.DataFrame(abl).to_string())
    print(pd.DataFrame(sens).to_string())
    print(pd.DataFrame(couts).to_string())


if __name__ == "__main__":
    main()
