"""Métriques orientées métier, évaluées PAR ÉVÉNEMENT (panne) et non par point.

* Une alarme n'est « utile » que si elle survient AVANT le début de la panne,
  dans la fenêtre d'anticipation [début - W, début[.
* Une alarme pendant la panne est « tardive » : elle ne compte PAS comme détection.
* Les alarmes successives espacées de moins de EPISODE_GAP sont regroupées en
  un seul épisode (l'atelier n'intervient qu'une fois).
* Fausse alerte = épisode qui démarre hors de toute fenêtre [début - W, maintenance + grâce].
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

FAILURES = pd.DataFrame([
    # id, début, fin, intervention atelier (rapport de l'exploitant, cf. Data Description)
    ("#1", "2020-04-18 00:00", "2020-04-18 23:59", "2020-04-18 23:59"),
    ("#2", "2020-05-29 23:30", "2020-05-30 06:00", "2020-05-30 12:00"),
    ("#3", "2020-06-05 10:00", "2020-06-07 14:30", "2020-06-08 16:00"),
    ("#4", "2020-07-15 14:30", "2020-07-15 19:00", "2020-07-16 00:00"),
], columns=["id", "start", "end", "maintenance"])
for _c in ["start", "end", "maintenance"]:
    FAILURES[_c] = pd.to_datetime(FAILURES[_c])

EPISODE_GAP = pd.Timedelta(hours=24)
GRACE = pd.Timedelta(hours=24)
DAYS_PER_MONTH = 30.44


def episodes(times: pd.Series) -> pd.DataFrame:
    t = pd.Series(sorted(times))
    if t.empty:
        return pd.DataFrame(columns=["start", "end", "n_alarms"])
    eid = (t.diff() > EPISODE_GAP).cumsum()
    return t.groupby(eid).agg(start="min", end="max", n_alarms="size").reset_index(drop=True)


def poisson_ci(k: int, exposure: float, alpha: float = 0.05):
    lo = 0.0 if k == 0 else stats.chi2.ppf(alpha / 2, 2 * k) / 2
    hi = stats.chi2.ppf(1 - alpha / 2, 2 * k + 2) / 2
    return float(lo / exposure), float(hi / exposure)


def clopper_pearson(k: int, n: int, alpha: float = 0.05):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return round(float(lo), 3), round(float(hi), 3)


def evaluate(cyc: pd.DataFrame, alarm: pd.Series, period: tuple, window_days: float = 7.0) -> dict:
    """cyc : cycles (avec decision_time) ; alarm : booléen aligné ; period : (début, fin)."""
    p0, p1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    W = pd.Timedelta(days=window_days)
    in_p = cyc["decision_time"].between(p0, p1)
    times = cyc.loc[in_p & alarm, "decision_time"]
    fails = FAILURES[(FAILURES["start"] > p0) & (FAILURES["start"] <= p1)]

    rows, excluded = [], pd.Series(False, index=times.index)
    for f in fails.itertuples():
        early = times[(times >= f.start - W) & (times < f.start)]
        late = times[(times >= f.start) & (times <= f.end)]
        rows.append({
            "panne": f.id, "debut": str(f.start),
            "detectee_avant": bool(len(early)),
            "avance_h": round((f.start - early.min()).total_seconds() / 3600, 1) if len(early) else None,
            "alarme_tardive_seulement": bool(len(late)) and not len(early),
        })
        excluded |= (times >= f.start - W) & (times <= f.maintenance + GRACE)

    ep = episodes(times[~excluded])
    # temps surveillé « sain » = période moins les fenêtres de panne, ramené aux jours avec données
    days_with_data = cyc.loc[in_p, "decision_time"].dt.normalize().nunique()
    excl_days = 0
    for f in fails.itertuples():
        excl_days += cyc.loc[in_p & cyc["decision_time"].between(f.start - W, f.maintenance + GRACE),
                             "decision_time"].dt.normalize().nunique()
    months = max(days_with_data - excl_days, 1) / DAYS_PER_MONTH
    n_fa = len(ep)
    k = sum(r["detectee_avant"] for r in rows)
    fa_rate = n_fa / months
    return {
        "periode": [str(p0.date()), str(p1.date())],
        "fenetre_anticipation_j": window_days,
        "n_pannes": len(rows),
        "n_detectees_avant": k,
        "rappel_evenement": (k / len(rows)) if rows else None,
        "rappel_IC95": list(clopper_pearson(k, len(rows))) if rows else None,
        "fausses_alertes": n_fa,
        "mois_sains_surveilles": round(months, 2),
        "FA_par_mois": round(fa_rate, 2),
        "FA_par_mois_IC95": [round(x, 2) for x in poisson_ci(n_fa, months)],
        "part_cycles_en_alarme": round(float(alarm[in_p].mean()), 4),
        # détecteur aléatoire émettant des épisodes au même rythme (processus de Poisson)
        "rappel_detecteur_aleatoire": round(1 - np.exp(-fa_rate / DAYS_PER_MONTH * window_days), 3),
        "pannes": rows,
    }
