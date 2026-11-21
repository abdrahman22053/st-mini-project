"""Détecteurs : baseline (résidu de prévision + seuil + persistance) et modèles plus riches.

Règle anti-fuite : tout ce qui est « appris » (Ridge, StandardScaler, Isolation
Forest, ACP, seuils) est ajusté UNIQUEMENT sur la période d'entraînement.
Les hyper-paramètres (quantile du seuil, persistance) sont choisis sur la
période de validation. La période de test n'est utilisée qu'une seule fois.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42

# Variables de contexte opérationnel (connues au moment du cycle et NON affectées
# par une fuite). La température d'huile est exclue : une fuite fait tourner le
# compresseur plus longtemps et la réchauffe -> elle « expliquerait » l'anomalie.
CONTEXT_COLS = ["hour_sin", "hour_cos", "is_weekend"]

FEATURE_GROUPS = {
    "duree": ["duration_s", "gain_rate"],
    "repos_fuite": ["idle_before_s", "leak_rate", "duty_cycle"],
    "thermique": ["oil_temp_max"],
    "electrique": ["current_mean", "current_max"],
    "tendances": ["duration_s_med15", "idle_before_s_med15", "leak_rate_med15", "duty_cycle_med15"],
}
ALL_FEATURES = [c for cols in FEATURE_GROUPS.values() for c in cols]


def add_context(cyc: pd.DataFrame) -> pd.DataFrame:
    h = cyc["start_time"].dt.hour + cyc["start_time"].dt.minute / 60
    cyc = cyc.copy()
    cyc["hour_sin"] = np.sin(2 * np.pi * h / 24)
    cyc["hour_cos"] = np.cos(2 * np.pi * h / 24)
    cyc["is_weekend"] = (cyc["start_time"].dt.dayofweek >= 5).astype(float)
    return cyc


def persist(raw: pd.Series, k: int) -> pd.Series:
    """Alarme si les k derniers cycles (fenêtre passée) sont tous au-dessus du seuil."""
    return raw.astype(float).rolling(k, min_periods=k).sum().eq(k)


# ---------------------------------------------------------------- baseline
class ResidualBaseline:
    """Prévoit le taux de chute de pression au repos (consommation d'air) à partir du
    seul contexte opérationnel, puis surveille le résidu positif lissé (EWMA causale)."""

    def __init__(self, target: str = "leak_rate", span: int = 10):
        self.target, self.span = target, span
        self.model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))

    def fit(self, train: pd.DataFrame):
        d = train.dropna(subset=[self.target])
        self.model.fit(d[CONTEXT_COLS], d[self.target])
        r = d[self.target] - self.model.predict(d[CONTEXT_COLS])
        self.sigma = float(r.std())
        self.train_scores = self.score(train)
        return self

    def score(self, df: pd.DataFrame) -> pd.Series:
        pred = self.model.predict(df[CONTEXT_COLS])
        z = (df[self.target] - pred) / self.sigma           # résidu standardisé (signé)
        z = z.fillna(0.0)                                   # début de session : pas d'info -> neutre
        return z.ewm(span=self.span, adjust=False).mean()   # EWMA : uniquement le passé


# ---------------------------------------------------------- modèles riches
class IForestDetector:
    def __init__(self, features=None, n_estimators: int = 200):
        self.features = list(features or ALL_FEATURES)
        self.pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        self.model = IsolationForest(n_estimators=n_estimators, random_state=SEED)

    def fit(self, train: pd.DataFrame):
        X = self.pipe.fit_transform(train[self.features])
        self.model.fit(X)
        self.train_scores = self.score(train)
        return self

    def score(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(-self.model.score_samples(self.pipe.transform(df[self.features])), index=df.index)


class PCADetector:
    """ACP : statistique SPE (erreur de reconstruction) + T² de Hotelling combinés."""

    def __init__(self, features=None, var: float = 0.9):
        self.features = list(features or ALL_FEATURES)
        self.pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        self.var = var

    def fit(self, train: pd.DataFrame):
        X = self.pipe.fit_transform(train[self.features])
        self.pca = PCA(n_components=self.var, random_state=SEED).fit(X)
        t2, spe = self._stats(X)
        self.t2_scale, self.spe_scale = np.median(t2), np.median(spe)
        self.train_scores = self.score(train)
        return self

    def _stats(self, X):
        T = self.pca.transform(X)
        t2 = (T**2 / self.pca.explained_variance_).sum(1)
        spe = ((X - self.pca.inverse_transform(T)) ** 2).sum(1)
        return t2, spe

    def score(self, df: pd.DataFrame) -> pd.Series:
        t2, spe = self._stats(self.pipe.transform(df[self.features]))
        return pd.Series(np.maximum(t2 / self.t2_scale, spe / self.spe_scale), index=df.index)
