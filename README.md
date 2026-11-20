# Sujet 5 : Surveillance Prédictive du Compresseur d'un Métro (Pannes Réelles)

**Projet :** Mini-projet de Séries Temporelles (M2 - S3)  
**Binôme Groupe 5 :** Abderahmane Abderrahmane & Hafssatou Bilal  
**Établissement :** SupNum (`22053@supnum.mr` / `22067@supnum.mr`)  
**Jeu de données :** UCI MetroPT-3 (Données réelles de l'Unité de Production d'Air du métro de Porto)

---

## Sommaire
1. [Contexte Métier & Objectifs](#1-contexte-métier--objectifs)
2. [Description Complète des Données (Colonnes & Pannes)](#2-description-complète-des-données)
3. [Diagnostic de la Grille & Traitement des Données (Question 1)](#3-diagnostic-de-la-grille--traitement-des-données-question-1)
4. [Indicateurs par Cycle de Compression & Période Saine (Question 2)](#4-indicateurs-par-cycle-de-compression--période-saine-question-2)
5. [Modèles de Détection : Baseline vs Modèle Avancé (Question 3)](#5-modèles-de-détection--baseline-vs-modèle-avancé-question-3)
6. [Frise Temporelle des Pannes & Avance d'Alerte P-F (Question 4)](#6-frise-temporelle-des-pannes--avance-dalerte-p-f-question-4)
7. [Arbitrage Économique : Fausse Alerte vs Panne en Ligne (Question 5)](#7-arbitrage-économique--fausse-alerte-vs-panne-en-ligne-question-5)
8. [Arborescence & Instructions d'Exécution](#8-arborescence--instructions-dexécution)

---

## 1. Contexte Métier & Objectifs

Dans un système ferroviaire urbain (métro), l'air comprimé produit par l'**APU (Air Production Unit)** est un organe critique de sécurité : il alimente le **système de freinage mécanique**, la **suspension pneumatique** et les **portes passagers**.

* **La problématique métier :** Si le compresseur subit une défaillance en service voyageur (ex. chute de pression critique sous 7 bars due à une fuite majeure), la rame s'immobilise d'urgence en pleine voie. Cela engendre des retards sur tout le réseau, des coûts de remorquage élevés et des pénalités financières.
* **L'objectif du projet :** Concevoir un système de détection précoce d'anomalies capable de lever une alerte **plusieurs heures ou jours avant** la défaillance totale, dans une **fenêtre utile pour l'atelier de maintenance** (permettant une intervention de nuit au dépôt sans perturber le trafic).

---

## 2. Description Complète des Données

Le dataset `MetroPT3(AirCompressor).csv` regroupe des enregistrements continus de capteurs du 1er février 2020 au 1er septembre 2020 (7 mois d'exploitation).

### 2.1. Tableau des Capteurs Analogiques (Grandeurs Physiques Continues)

| N° | Variable | Unité | Plage typique | Description & Signification Physique | Rôle pour la détection de fuite |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **1** | `TP2` | bar | $-0.02$ à $10.5$ | Pression interne mesurée directement en sortie du compresseur. | Permet de vérifier si le compresseur monte correctement en pression lorsqu'il est commandé. |
| **2** | `TP3` | bar | $8.0$ à $10.2$ | Pression au panneau pneumatique de distribution générale. | Indique la pression disponible pour les sous-systèmes du train. |
| **3** | `H1` | bar | $8.0$ à $10.2$ | Pression au niveau du filtre séparateur cyclonique. | Chute lors des phases de purge d'eau et de résidus d'huile. |
| **4** | `DV_pressure` | bar | $-0.02$ à $10.0$ | Chute de pression lors de la purge des tours de séchage d'air. | Vaut $\approx 0$ bar quand le compresseur produit en charge. |
| **5** | `Reservoirs` | bar | $8.0$ à $10.2$ | **Pression dans les réservoirs principaux d'air.** | **Grandeur clé :** monte de 8.2 à 10 bar pendant la compression. Si elle chute trop vite au repos, il y a une fuite. |
| **6** | `Oil_temperature`| °C | $45$ à $85$ | Température de l'huile de lubrification du compresseur. | Une fuite ou un frottement anormal force le compresseur à tourner plus longtemps, augmentant la température. |
| **7** | `Motor_current` | A | $0.0$ à $9.5$ | Courant absorbé par une phase du moteur électrique triphasé. | 0 A = Arrêt ; $\approx 3.8$ A = À vide ; $\ge 7.0$ A = En compression active ; $\approx 9$ A = Démarrage. |

### 2.2. Tableau des Capteurs Digitaux (Signaux Tout-Ou-Rien / Binaires)

| N° | Variable | Valeurs | État 0 | État 1 | Signification & Rôle Opérationnel |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **8** | `COMP` | 0 ou 1 | **Admission d'air ouverte** (compression active) | Vanne fermée (compresseur éteint ou à vide) | Signal électrique de commande d'admission. Inversé par rapport à l'effort de compression. |
| **9** | `DV_eletric` | 0 ou 1 | Vanne de décharge fermée | **Vanne de refoulement active** | Actif lorsque le compresseur refoule l'air sous pression vers les cuves. |
| **10** | `Towers` | 0 ou 1 | Tour de séchage n°1 active | Tour de séchage n°2 active | Alterne le cycle d'assèchement entre les deux colonnes déshydratantes. |
| **11** | `MPG` | 0 ou 1 | Pression normale | **Démarrage automatique (P < 8.2 bar)** | Déclenche automatiquement le cycle de compression dès que la pression passe sous 8.2 bar. |
| **12** | `LPS` | 0 ou 1 | Pression normale | **Urgence Basse Pression (P < 7.0 bar)** | Alarme de sécurité critique si la pression s'effondre sous le seuil d'urgence. |
| **13** | `Pressure_switch`| 0 ou 1 | Repos | Décharge active | Capteur de purge des tours de dessiccation. |
| **14** | `Oil_level` | 0 ou 1 | Niveau d'huile OK | **Alerte : Niveau d'huile trop bas** | Sécurité de lubrification du groupe moteur-compresseur. |
| **15** | `Caudal_impulses`| 0 ou 1 | Repos | Impulsion de débit | Compteur d'impulsions traduisant le volume absolu d'air débité. |

### 2.3. Tableau des Défaillances Réelles Documentées (Vérité Terrain)

Les pannes réelles répertoriées dans le rapport officiel d'exploitation :

| N° Panne | Début de l'incident | Fin de l'incident | Intervention Atelier | Type d'avarie | Gravité constatée |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **#1** | 18/04/2020 00:00 | 18/04/2020 23:59 | 18/04/2020 | Fuite d'air (*Air leak*) | Contrainte mécanique élevée (*High stress*) |
| **#2** | 29/05/2020 23:30 | 30/05/2020 06:00 | 30/05/2020 à 12:00 | Fuite d'air (*Air leak*) | Contrainte mécanique élevée (*High stress*) |
| **#3** | 05/06/2020 10:00 | 07/06/2020 14:30 | 08/06/2020 à 16:00 | Fuite d'air (*Air leak*) | Contrainte mécanique élevée (*High stress*) |
| **#4** | 15/07/2020 14:30 | 15/07/2020 19:00 | 16/07/2020 à 00:00 | Fuite d'air (*Air leak*) | Contrainte mécanique élevée (*High stress*) |

---

## 3. Diagnostic de la Grille & Traitement des Données (Question 1)

### 3.1. Analyse de la Grille Temporelle
* **Fréquence d'origine vs fichier CSV :** Alors que les capteurs physiques échantillonnent à **1 Hz** (1 mesure/seconde, soit $\approx 15$ millions de lignes), le fichier `MetroPT3(AirCompressor).csv` a été décimé à **un pas régulier de 10 secondes** ($\Delta t = 10\text{ s}$, médiane exacte), soit 1 516 948 lignes.
* **Diagnostic des "trous" temporels (Gaps) :** L'analyse révèle **331 coupures de plus de 60 secondes**, totalisant 909 heures d'arrêt.
  * **Interprétation :** Ces coupures correspondent aux extinctions nocturnes de la rame lorsqu'elle est garée au dépôt (entre 01h et 05h).
  * **Décision de traitement :** **Aucune imputation par interpolation**, car la rame était physiquement hors tension. Le compresseur ne tournait pas.

### 3.2. Diagnostic des Régimes de Fonctionnement

| Régime | Conditions capteurs | Courant moteur | Proportion du temps | Rôle dans l'analyse |
| :--- | :--- | :---: | :---: | :--- |
| **1. Arrêt complet** | `Motor_current < 0.5 A` | $\approx 0.04$ A | **69.7 %** | Rame en stationnement ou maintien de pression. |
| **2. À vide (Offloaded)** | `Motor_current` entre 1 et 5 A, `COMP = 1` | $\approx 3.8$ A | **23.9 %** | Le moteur tourne sans entraîner la compression d'air. |
| **3. En charge (Compression)** | `Motor_current > 5.5 A` ou `COMP = 0`, `DV_eletric = 1` | $\ge 7.0$ A | **6.4 %** | **Production active d'air sous pression.** |

### 3.3. Comparaison et Justification du Rééchantillonnage

| Méthode de Rééchantillonnage | Avantages | Inconvénients | Verdict |
| :--- | :--- | :--- | :---: |
| **Temporel fixe (ex. 10 min ou 1h)** | Simple à coder. | Écrase la dynamique de compression qui ne dure que 2 minutes tous les quarts d'heure. | **Rejeté** |
| **Segmentation par Cycle Physique** | Respecte la physique du compresseur, capture la durée exacte de montée en pression et la vitesse de vidange. | Nécessite un algorithme de découpage robuste aux coupures nocturnes. | **Retenu (Optimal)** |

---

## 4. Indicateurs par Cycle de Compression & Période Saine (Question 2)

Un cycle de compression correspond à l'intervalle où le compresseur s'enclenche pour regonfler les réservoirs de $\approx 8.2$ bar à $10.1$ bar.

### 4.1. Indicateurs Extraits par Cycle

| Indicateur | Définition mathématique / physique | Comportement normal | Comportement lors d'une fuite |
| :--- | :--- | :--- | :--- |
| `duration_sec` | $t_{fin} - t_{debut}$ du cycle actif | $\approx 120$ s ($\pm 40$ s) | **Augmente fortement** (le compresseur peine à remplir les cuves). |
| `pressure_gain` | $P_{fin} - P_{debut}$ (en bar) | $\approx 1.9$ bar | Reste similaire ou diminue si la fuite compense le débit. |
| `idle_sec` | Temps de repos avant le cycle suivant | 15 à 30 minutes | **Diminue** (les cuves se dégonflent plus vite $\to$ cycles plus fréquents). |
| `max_oil_temp` | $\max(Oil\_temperature)$ pendant le cycle | $50$ à $65$ °C | **Augmente** (surchauffe par fonctionnement prolongé). |
| `mean_motor_current`| $\frac{1}{N}\sum Motor\_current$ | $7.2$ à $7.8$ A | Légère surconsommation en charge prolongée. |

### 4.2. Définition de la Période Saine
* **Période d'entraînement (Normale) :** Du **1er février 2020 au 31 mars 2020** ($\approx 2\,700$ cycles physiques). Aucun événement ni alerte de maintenance n'est consigné durant ces 2 mois.
* **Période de test (Surveillance) :** Du **1er avril 2020 au 31 août 2020** (contenant les 4 fuites documentées).

---

## 5. Modèles de Détection : Baseline vs Modèle Avancé (Question 3)

### 5.1. Tableau Comparatif des Deux Détecteurs

| Caractéristique | Baseline Exigée | Détecteur Avancé (Isolation Forest) |
| :--- | :--- | :--- |
| **Type d'algorithme** | Régression Ridge (modèle physique) + Résidu | Forêt d'arbres d'isolation non-supervisée multivariée |
| **Variables d'entrée** | `pressure_gain`, `max_oil_temp` $\to$ prédit `duration_sec` | 5 variables : durée, gain, repos inter-cycle, température, courant |
| **Score d'anomalie** | Résidu absolu : $e_i = \|D_i - \hat{D}_i\|$ | Score d'isolation : $s(x) = -\text{score\_samples}(x)$ |
| **Seuil de déclenchement** | Statistique : $\tau = \mu_{train} + 3 \cdot \sigma_{train}$ (3 sigmas) | Percentile 99 sur la période saine |
| **Persistance temporelle** | Alerte si $e_i > \tau$ pendant **3 cycles consécutifs** | Alerte si $s(x) > \tau_{IF}$ pendant **3 cycles consécutifs** |

> **Rôle fondamental de la persistance temporelle :** Une seule mesure anormale peut provenir d'un aléa ponctuel (ex. ouverture prolongée des portes lors d'une forte affluence). Exiger 3 cycles anormaux consécutifs permet de filtrer ces bruits sans masquer la dérive lente caractéristique d'une fuite d'air.

---

## 6. Frise Temporelle des Pannes & Avance d'Alerte P-F (Question 4)

### 6.1. Lien avec la Courbe P-F en Maintenance Conditionnelle

```
État du Compresseur
 ▲
 │ ────── P (Défaut potentiel naissant : micro-fuite, durée de cycle qui dérive)
 │        \
 │         \  <=== Fenêtre d'alerte utile (Atelier intervient de nuit au dépôt)
 │          \
 │           \────── F (Panne fonctionnelle : train immobilisé en pleine ligne)
 └────────────────────────────────────────────────────────► Temps
```

* **Point P (*Potential failure*) :** Moment où l'anomalie physique devient mesurable par les capteurs (allongement de la durée de cycle, réduction du temps de repos).
* **Point F (*Functional failure*) :** Panne déclarée et bloquante en service.
* **Avance d'alerte ($\Delta t = t_F - t_{alarme}$) :** Temps disponible pour l'équipe de maintenance pour planifier le retrait de la rame vers l'atelier sans perturber l'exploitation.

### 6.2. Performances et Détections Réelles Obtenues

| Événement | Date Début Panne | Détection Baseline | Avance Baseline | Détection Isolation Forest | Avance Isolation Forest |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Panne #1** | 18/04/2020 00:00 | Détectée | En cours de journée | Détectée | En cours de journée |
| **Panne #2** | 29/05/2020 23:30 | Détectée | $> 24$ heures | **Détectée** | **89.5 heures ($\approx 3.7$ jours)** |
| **Panne #3** | 05/06/2020 10:00 | Détectée | Dès l'apparition | Détectée | Dès l'apparition |
| **Panne #4** | 15/07/2020 14:30 | **Détectée** | **0.9 heure** | **Détectée** | **0.4 heure** |

*Pour la panne #2, le détecteur avancé Isolation Forest lève une alerte persistante près de 4 jours avant la panne déclarée, offrant une fenêtre de maintenance parfaite.*

---

## 7. Arbitrage Économique : Fausse Alerte vs Panne en Ligne (Question 5)

En contexte ferroviaire, le coût d'une erreur n'est absolument pas symétrique.

### 7.1. Matrice des Coûts d'Exploitation

| Cas | Situation | Conséquence opérationnelle | Coût unitaire estimé |
| :---: | :--- | :--- | :---: |
| **Vrai Positif (TP)** | Alerte justifiée $\to$ Fuite réparée | Rentrée nocturne au dépôt, échange de joint/valve par un technicien. | $\approx 200$ € |
| **Faux Positif (FP)** | Fausse alerte | Inspection visuelle rapide au dépôt lors de la rentrée normale. Train disponible. | $\approx 150$ € |
| **Faux Négatif (FN)** | **Panne non détectée en ligne** | **Train immobilisé en pleine voie, blocage de la ligne, remorquage, pénalités de retard.** | **$10\,000$ à $50\,000$ €** |

### 7.2. Modélisation du Coût Total
$$\text{Coût Total} = N_{FP} \times C_{FP} + N_{FN} \times C_{FN}$$

Puisque $\frac{C_{FN}}{C_{FP}} \approx 100$, il est **100 fois plus pénalisant de rater une panne que de déclencher une fausse alerte**.  
* **Stratégie retenue :** Viser un **rappel de 100 % sur les pannes critiques** ($N_{FN} = 0$).
* **Maîtrise des fausses alertes :** Sur la période saine de référence (février-mars), la baseline enregistre **0.0 fausse alerte par mois** et l'Isolation Forest enregistre **0.5 fausse alerte par mois**, respectant largement la contrainte opérationnelle d'un atelier ferroviaire.

---

## 8. Arborescence & Instructions d'Exécution

### 8.1. Contenu du Répertoire

```text
metropt+3+dataset/
├── README.md                              <- Ce document explicatif complet
├── sujet5_surveillance_compresseur.ipynb  <- Le notebook Jupyter complet et exécutable
├── MetroPT3(AirCompressor).csv            <- Données de capteurs réelles (1.5M lignes)
├── Data Description_Metro.pdf             <- Fiche descriptive officielle UCI
└── frise_chronologique_metro.png          <- Graphique des détections et frise des pannes
```

### 8.2. Lancer le Projet

1. **Vérifier l'environnement Python :**
   ```bash
   pip install pandas numpy matplotlib scikit-learn
   ```
2. **Ouvrir et exécuter le notebook :**
   * Dans **VS Code / Cursor** : ouvrir `sujet5_surveillance_compresseur.ipynb` et cliquer sur **Run All** (Tout exécuter).
   * Ou via terminal avec Jupyter :
     ```bash
     jupyter notebook sujet5_surveillance_compresseur.ipynb
     ```

