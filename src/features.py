"""Préparation causale des données MetroPT-3 et indicateurs par cycle de compression.

Toutes les grandeurs d'un cycle i sont calculées uniquement avec des mesures
dont l'horodatage est <= fin du cycle i  (aucune information future).
L'instant de décision d'un cycle est donc sa date de FIN (`end_time`).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

SESSION_GAP_S = 60       # au-delà : coupure (rame éteinte) -> nouvelle session
MIN_DURATION_S = 20      # cycle de charge plausible
MAX_DURATION_S = 1800
MAX_IDLE_S = 3 * 3600    # repos plausible entre deux cycles d'une même session
ROLL_N = 15              # fenêtre glissante PASSÉE (en cycles) pour les tendances


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    n0 = len(df)
    df = df.sort_values("timestamp")
    n_dup = int(df["timestamp"].duplicated().sum())
    df = df.drop_duplicates("timestamp").reset_index(drop=True)
    log.info("Chargement : %d lignes, %d horodatages dupliqués supprimés, %d NaN",
             n0, n_dup, int(df.isna().sum().sum()))
    return df


def diagnose_grid(df: pd.DataFrame) -> dict:
    dt = df["timestamp"].diff().dt.total_seconds()
    gaps = dt[dt > SESSION_GAP_S]
    regime = np.select(
        [df["Motor_current"] < 0.5, df["COMP"] == 0],
        ["arret", "charge"], default="vide")
    out = {
        "n_rows": len(df),
        "start": str(df["timestamp"].min()),
        "end": str(df["timestamp"].max()),
        "dt_median_s": float(dt.median()),
        "dt_share_9_13s": float(dt.between(9, 13).mean()),
        "n_duplicated_ts": int(df["timestamp"].duplicated().sum()),
        "n_missing_values": int(df.isna().sum().sum()),
        "n_gaps_gt_60s": int(len(gaps)),
        "gap_hours_total": float(gaps.sum() / 3600),
        "n_gaps_gt_1h": int((gaps > 3600).sum()),
        "max_gap_hours": float(gaps.max() / 3600),
        "regime_share": pd.Series(regime).value_counts(normalize=True).round(4).to_dict(),
    }
    return out


def build_cycles(df: pd.DataFrame) -> pd.DataFrame:
    """Segmente la série en cycles de charge (COMP == 0, admission ouverte).

    Une coupure > SESSION_GAP_S ferme la session : aucun cycle ne la traverse
    et aucune grandeur inter-cycle n'est calculée à travers une coupure.
    """
    ts = df["timestamp"]
    dt = ts.diff().dt.total_seconds().fillna(np.inf)
    new_session = dt > SESSION_GAP_S
    session_id = new_session.cumsum()
    loading = df["COMP"].eq(0)
    change = loading.ne(loading.shift()) | new_session
    run_id = change.cumsum()

    g = df[loading].assign(run_id=run_id[loading], session_id=session_id[loading]).groupby("run_id")
    cyc = g.agg(
        session_id=("session_id", "first"),
        start_time=("timestamp", "first"),
        end_time=("timestamp", "last"),
        n_samples=("timestamp", "size"),
        p_start=("Reservoirs", "first"),
        p_end=("Reservoirs", "last"),
        tp2_max=("TP2", "max"),
        oil_temp_start=("Oil_temperature", "first"),
        oil_temp_max=("Oil_temperature", "max"),
        current_mean=("Motor_current", "mean"),
        current_max=("Motor_current", "max"),
    ).reset_index(drop=True)
    cyc["duration_s"] = (cyc["end_time"] - cyc["start_time"]).dt.total_seconds()
    cyc["pressure_gain"] = cyc["p_end"] - cyc["p_start"]

    n_all = len(cyc)
    ok = cyc["duration_s"].between(MIN_DURATION_S, MAX_DURATION_S) & (cyc["pressure_gain"] > 0.3)
    cyc = cyc[ok].reset_index(drop=True)
    log.info("Cycles de charge : %d détectés, %d gardés après filtre physique", n_all, len(cyc))

    cyc["gain_rate"] = cyc["pressure_gain"] / cyc["duration_s"] * 60  # bar/min

    # --- Grandeurs inter-cycles : uniquement avec le cycle PRÉCÉDENT (causal) ---
    prev_end = cyc["end_time"].shift(1)
    prev_p_end = cyc["p_end"].shift(1)
    same_session = cyc["session_id"].eq(cyc["session_id"].shift(1))
    idle = (cyc["start_time"] - prev_end).dt.total_seconds()
    valid = same_session & idle.between(1, MAX_IDLE_S)
    cyc["idle_before_s"] = idle.where(valid)
    # vitesse de chute de pression des réservoirs pendant le repos (fuite !)
    cyc["leak_rate"] = ((prev_p_end - cyc["p_start"]) / idle * 60).where(valid)  # bar/min
    # rapport de service : part du temps en charge sur (repos + charge)
    cyc["duty_cycle"] = (cyc["duration_s"] / (cyc["duration_s"] + idle)).where(valid)
    log.info("Grandeurs inter-cycles manquantes (début de session) : %d (laissées NaN, pas de bfill)",
             int(cyc["idle_before_s"].isna().sum()))

    # --- Tendances glissantes sur les ROLL_N cycles passés (fenêtre à gauche) ---
    for col in ["duration_s", "idle_before_s", "leak_rate", "duty_cycle"]:
        cyc[f"{col}_med{ROLL_N}"] = cyc[col].rolling(ROLL_N, min_periods=5).median()
    cyc["decision_time"] = cyc["end_time"]
    return cyc
