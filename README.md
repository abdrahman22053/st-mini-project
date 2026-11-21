# Sujet 5 — Surveiller le compresseur d'un métro (pannes réelles)

**AML313 · Séries temporelles de capteurs IoT · Master SupNum — Groupe 5**
Abderahmane Abderrahmane (22053) · Hafssatou Bilal (22067)
Données : [UCI MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset) (unité de production d'air d'un train du métro de Porto, févr.–sept. 2020)

> **Question métier :** alerter *avant* une défaillance du compresseur, dans une fenêtre utile pour l'atelier.
> **Baseline exigée :** résidu de prévision + seuil + persistance. **Métriques :** rappel par événement, avance d'alerte (P-F), fausses alertes par mois.

---

## Tout relancer : une seule commande

```bash
bash run_all.sh
```

Cette commande :
1. crée un environnement virtuel figé `.venv` à partir de `requirements.txt` (Python ≥ 3.11) ;
2. télécharge le CSV officiel depuis l'UCI et **vérifie son empreinte SHA-256** (`src/download_data.py`) ;
3. exécute le pipeline complet (`src/run_pipeline.py`, graines fixées à 42) : diagnostic, cycles causaux, découpage train → gap → validation → gap → test, réglage sur la validation, **évaluation unique sur le test**, ablation et figures ;
4. ré-exécute le notebook `sujet5_surveillance_compresseur.ipynb` de bout en bout.

L'exécution dure environ 1 min, hors installation et téléchargement (~220 Mo). Pour utiliser le Python courant au lieu du venv : `SKIP_VENV=1 bash run_all.sh` (ou `make all`).

## Arborescence

```text
st-mini-project/
├── run_all.sh                     <- commande unique (venv + données + pipeline + notebook)
├── Makefile                       <- raccourcis : make all / data / pipeline / notebook
├── requirements.txt               <- versions figées
├── sujet5_surveillance_compresseur.ipynb   <- notebook commenté (exécuté)
├── src/
│   ├── download_data.py           <- téléchargement UCI + vérification SHA-256
│   ├── features.py                <- chargement, diagnostic de grille, cycles CAUSAUX
│   ├── detectors.py               <- baseline (résidu Ridge + EWMA), Isolation Forest, ACP T²/SPE
│   ├── evaluation.py              <- métriques par événement, épisodes, IC 95 %, détecteur aléatoire
│   ├── figures.py                 <- figures du rapport
│   └── run_pipeline.py            <- orchestration : split avec gap, réglage val, test unique, ablation
├── results/                       <- sorties régénérées (CSV, JSON, log, figures/)
├── rapport/rapport.pdf            <- article court (5 pages) ; source rapport.md, build.sh
├── presentation/soutenance.pptx   <- diapositives de soutenance (10 min) + PDF ; make_slides.py
├── Data Description_Metro.pdf     <- fiche officielle UCI (capteurs + rapport des pannes)
└── data/                          <- CSV téléchargé (ignoré par git)
```

## Protocole (résumé)

| Étape | Choix | Garde-fou anti-fuite |
|---|---|---|
| Diagnostic | Pas réel ~10 s (fichier décimé), 0 doublon, 0 NaN, 331 coupures > 60 s (909 h) | Coupure = fin de session ; **aucune imputation** à travers une coupure |
| Agrégat | **1 ligne par cycle de compression** (`COMP = 0`), 10 751 cycles | L'instant de décision est la **fin** du cycle |
| Indicateurs | durée, vitesse de charge, repos depuis le cycle **précédent**, chute de pression au repos, rapport de service, T° huile, courant, médianes sur les **15 cycles passés** | Aucun `bfill`, aucune fenêtre centrée ; test automatique de causalité dans le notebook |
| Découpage | Train 01/02–31/03 · gap 3 j · Val 04/04–10/05 (panne #1) · gap 3 j · Test 14/05–01/09 (pannes #2, #3, #4) | Gap 3 j > mémoire des indicateurs ; assertions dans le code |
| Apprentissage | Scaler, Ridge, IF, ACP et seuils ajustés sur le **train seul** (10 jours aberrants de mars exclus, règle calculée sur le train) | — |
| Réglage | Quantile q et persistance K choisis sur la **validation** (FA ≤ 2/mois → rappel max → plus sensible) | Le **test n'est utilisé qu'une fois** |
| Métriques | Rappel par événement (alarme dans [début − 7 j, début[), avance d'alerte, épisodes de FA/mois, IC 95 %, comparaison au hasard | Une alarme **pendant** la panne est tardive et ne compte pas |

## Résultats (test, utilisé une seule fois)

| Détecteur | Pannes détectées avant | FA / mois [IC 95 %] | % cycles en alarme | Coût test* |
|---|:-:|:-:|:-:|:-:|
| **Baseline** (résidu Ridge + EWMA) | **3/3** | **5,4** [3,0 ; 9,1] | **15,7 %** | **2 700 €** |
| Isolation Forest | 3/3 | 7,3 [4,4 ; 11,4] | 34,5 % | 3 450 € |
| ACP (T² / SPE) | 3/3 | 5,8 [3,2 ; 9,5] | 22,0 % | 2 850 € |
| Aucune surveillance | 0/3 | – | – | 60 000 € |

\* Hypothèses : FA 150 €, réparation planifiée 200 €, panne en ligne 20 000 €. IC du rappel 3/3 : [0,29 ; 1].

* La panne #1 (validation) n'est détectée par aucun modèle : les capteurs sont figés dès le 17/04 et il n'y a pas de dérive préalable.
* Avant la panne #2, la consommation d'air au repos double **12 jours avant** : le point P est très en amont de F.
* Le taux de fausses alertes s'explique par une **dérive durable** de la consommation d'air à partir de mi-mai (voir *Limites* dans le rapport).
* **Ablation** : les 3 indicateurs « repos / fuite » suffisent (3/3, 5,0 FA/mois). Sans les tendances, on a 4 fois moins de FA mais la panne #2 est manquée.

Détails : `results/metriques_par_split.csv`, `detection_par_panne.csv`, `ablation.csv`, `sensibilite_fenetre.csv`, `couts_test.csv`, `pipeline.log`.

---

## Conformité aux consignes du professeur : ce qui manquait et ce qui a été fait

Audit de la version initiale du dépôt (commit `c6c8e54`) au regard du document *Mini-projet AML313* (cadre commun, livrables, grille d'évaluation et Sujet 5).

| Exigence du sujet | Version initiale | Correction apportée |
|---|---|---|
| **Éliminatoire : aucune fuite temporelle** | ❌ `idle_sec` calculé avec le cycle **suivant** puis `bfill()` ; alarme datée au début du cycle | ✅ Grandeurs calculées avec le cycle **précédent**, NaN laissés tels quels, décision à la fin du cycle, test automatique de causalité |
| Validation chronologique **avec gap**, test-set utilisé **une seule fois** | ❌ Train/test seulement, pas de validation ni de gap ; seuils réglés sans jeu indépendant | ✅ Train → gap 3 j → validation → gap 3 j → test, avec assertions ; réglage sur validation ; test évalué une fois |
| Baseline et hypothèse **écrites avant tout modèle** | ⚠️ Implicites | ✅ Écrites dans le notebook (phase 1) et le rapport §3 |
| Préparation **journalisée** | ❌ Absente | ✅ `results/pipeline.log` (lignes, coupures, cycles filtrés, NaN, jours exclus, choix des hyper-paramètres) |
| Diagnostic : grille, doublons, manquants, **mécanisme** | ⚠️ Partiel (régimes estimés sur les 100 000 premières lignes seulement) | ✅ Diagnostic complet sur tout le fichier, mécanisme des manquants discuté |
| Modèle plus riche **+ ablation** | ⚠️ Isolation Forest seule (ACP importée mais pas utilisée), pas d'ablation | ✅ Isolation Forest + ACP (T²/SPE) ; ablation par groupe de capteurs |
| Métriques : **rappel par événement, avance, FA/mois** | ❌ Alarme pendant la panne comptée comme détection ; FA comptées sur les données d'entraînement ; pas d'épisodes | ✅ Seules les alarmes **avant** la panne comptent ; FA mesurées sur val/test, regroupées en épisodes |
| Résultats **avec incertitude** | ❌ Absents | ✅ IC 95 % Clopper-Pearson et Poisson, comparaison au détecteur aléatoire, sensibilité à la fenêtre W |
| Lien avec la décision métier (coût FA vs panne) | ⚠️ Discussion qualitative | ✅ Coût chiffré sur le test (`couts_test.csv`) |
| **Dépôt reproductible : une seule commande, environnement figé, graines, README** | ❌ CSV absent du dépôt, pas de `requirements.txt`, exécution manuelle du notebook, README annonçant un fichier absent | ✅ `bash run_all.sh`, `requirements.txt` figé, téléchargement + SHA-256, graine 42, README à jour |
| **Article court (4–6 pages)** avec dates de coupure, protocole, résultats, ablation, « Limites » | ❌ Absent | ✅ `rapport/rapport.pdf` (5 pages) |
| **Soutenance 10 min** | ❌ Absente | ✅ `presentation/soutenance.pptx` (+ PDF), 12 diapositives |
| Chiffres annoncés vérifiables | ❌ Résultats du README non reproductibles (ex. « 0 FA/mois », mesuré sur le train) | ✅ Tous les chiffres sont générés par le pipeline dans `results/` |

### Ce qui reste à faire par le binôme

* Relire le rapport et la présentation, et les adapter à votre façon de présenter. **Vous devez pouvoir expliquer chaque choix à l'oral.**
* Remplir la grille du document du professeur (noms, matricules) si elle est demandée.
* Les coûts (150 € / 200 € / 20 000 €) sont des hypothèses d'ordre de grandeur, à présenter comme telles.
