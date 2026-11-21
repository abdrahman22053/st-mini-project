"""Figures du rapport (matplotlib, rendu non interactif)."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SPLIT_COLORS = {"train": "#d9ead3", "val": "#fff2cc", "test": "#dae8fc"}
FAIL_COLOR = "#c0392b"


def _decorate(ax, splits, failures, label=True):
    for s, (a, b) in splits.items():
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=SPLIT_COLORS[s], alpha=0.6, zorder=0,
                   label=s if label else None)
    for i, f in enumerate(failures.itertuples()):
        ax.axvspan(f.start, f.end, color=FAIL_COLOR, alpha=0.5, zorder=1,
                   label="panne documentée" if (label and i == 0) else None)
        ax.axvline(f.start, color=FAIL_COLOR, lw=1)


def make_all(df, cyc, dets, chosen, splits, failures, out):
    # 1. Grille temporelle et coupures
    dt = df["timestamp"].diff().dt.total_seconds()
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.5))
    dt.clip(upper=30).hist(bins=30, ax=ax[0], color="#4a6fa5")
    ax[0].set_title("Pas d'échantillonnage (s, tronqué à 30)")
    gaps = df.loc[dt > 60, "timestamp"]
    ax[1].scatter(gaps, dt[dt > 60] / 3600, s=8, color="#4a6fa5")
    ax[1].set_yscale("log"); ax[1].set_title("Coupures > 60 s (durée en h)")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out / "01_grille.png", dpi=130); plt.close(fig)

    # 2. Indicateurs journaliers par cycle
    d = cyc.set_index("decision_time")[["duration_s", "leak_rate", "duty_cycle", "oil_temp_max"]].resample("D").median()
    fig, axes = plt.subplots(4, 1, figsize=(13, 9), sharex=True)
    labels = ["Durée de charge (s)", "Chute de pression au repos (bar/min)", "Rapport de service", "T° huile max (°C)"]
    for ax, col, lab in zip(axes, d.columns, labels):
        _decorate(ax, splits, failures, label=(col == "duration_s"))
        ax.plot(d.index, d[col], color="#1f3b63", lw=1.2); ax.set_ylabel(lab, fontsize=8)
    axes[0].legend(loc="upper left", ncol=5, fontsize=8)
    axes[0].set_title("Indicateurs par cycle de compression (médiane journalière)")
    fig.tight_layout(); fig.savefig(out / "02_indicateurs_cycles.png", dpi=130); plt.close(fig)

    # 3. Frise : score + seuil + alarmes pour chaque détecteur
    fig, axes = plt.subplots(len(dets), 1, figsize=(13, 3 * len(dets)), sharex=True)
    for ax, name in zip(axes, dets):
        s = cyc[f"score::{name}"]; a = cyc[f"alarm::{name}"]
        _decorate(ax, splits, failures, label=(ax is axes[0]))
        ax.plot(cyc["decision_time"], s, lw=0.4, color="#555")
        ax.axhline(chosen[name]["seuil"], color="darkorange", ls="--", lw=1.2, label="seuil")
        ax.scatter(cyc.loc[a, "decision_time"], s[a], s=6, color="purple", zorder=3, label="alarme")
        hi = s.quantile(0.999) * 1.5
        ax.set_ylim(s.min(), hi)
        ax.set_title(f"{name} — q={chosen[name]['quantile']}, K={chosen[name]['persistance']}", fontsize=10)
    axes[0].legend(loc="upper left", ncol=7, fontsize=8)
    fig.tight_layout(); fig.savefig(out / "03_frise_detections.png", dpi=130); plt.close(fig)

    # 4. Zoom sur les 7 jours précédant chaque panne
    fig, axes = plt.subplots(len(failures), 1, figsize=(13, 2.6 * len(failures)))
    for ax, f in zip(axes, failures.itertuples()):
        w = cyc["decision_time"].between(f.start - pd.Timedelta(days=8), f.maintenance + pd.Timedelta(days=1))
        sub = cyc[w]
        ax.axvspan(f.start - pd.Timedelta(days=7), f.start, color="#e8f5e9", label="fenêtre utile (7 j)")
        ax.axvspan(f.start, f.end, color=FAIL_COLOR, alpha=0.4, label="panne")
        ax.plot(sub["decision_time"], sub["leak_rate"], ".", ms=2, color="#1f3b63", label="chute de pression au repos")
        ax.set_ylabel("bar/min", fontsize=8); ax.set_title(f"Panne {f.id} ({f.start:%d/%m/%Y %H:%M})", fontsize=10)
        for name, mk in zip(dets, ["v", "^", "s"]):
            a = sub[sub[f"alarm::{name}"]]
            ax.plot(a["decision_time"], [ax.get_ylim()[1] * 0.95] * len(a), mk, ms=4, ls="", label=name)
    axes[0].legend(fontsize=7, ncol=3, loc="upper left")
    fig.tight_layout(); fig.savefig(out / "04_zoom_pannes.png", dpi=130); plt.close(fig)
