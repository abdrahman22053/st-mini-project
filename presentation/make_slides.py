"""Génère soutenance.pptx (10 min) à partir des résultats du pipeline.

    python presentation/make_slides.py      (après bash run_all.sh ; nécessite python-pptx)
"""
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
RES, FIG = ROOT / "results", ROOT / "results" / "figures"
NAVY, GREY, RED = RGBColor(0x1F, 0x3B, 0x63), RGBColor(0x44, 0x44, 0x44), RGBColor(0xC0, 0x39, 0x2B)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W = prs.slide_width


def text(slide, x, y, w, h, lines, size=18, color=GREY, bold_first=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        bullet = line.startswith("- ")
        p.text = ("• " + line[2:]) if bullet else line
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.bold = bold_first and i == 0
        p.space_after = Pt(6)
    return tb


def slide(title, num):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    t = text(s, 0.5, 0.3, 12.3, 0.8, [title], size=28, color=NAVY)
    t.text_frame.paragraphs[0].font.bold = True
    text(s, 11.6, 7.0, 1.5, 0.4, [f"{num}"], size=11)
    text(s, 0.5, 7.0, 8, 0.4, ["AML313 · Groupe 5 · Sujet 5 — MetroPT-3"], size=11)
    return s


def table(s, df, x, y, w, h, size=13):
    shp = s.shapes.add_table(len(df) + 1, len(df.columns), Inches(x), Inches(y), Inches(w), Inches(h))
    tb = shp.table
    for j, c in enumerate(df.columns):
        cell = tb.cell(0, j); cell.text = str(c)
        cell.text_frame.paragraphs[0].font.size = Pt(size); cell.text_frame.paragraphs[0].font.bold = True
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, v in enumerate(row):
            cell = tb.cell(i, j); cell.text = str(v)
            cell.text_frame.paragraphs[0].font.size = Pt(size)
    return tb


def pic(s, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return s.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


m = pd.read_csv(RES / "metriques_par_split.csv")
abl = pd.read_csv(RES / "ablation.csv")
sens = pd.read_csv(RES / "sensibilite_fenetre.csv")
couts = pd.read_csv(RES / "couts_test.csv")
n = 0

# 1 ─ Titre
s = prs.slides.add_slide(BLANK); n += 1
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
text(s, 0.8, 2.0, 11.5, 1.5, ["Surveiller le compresseur d'un métro"], size=40, color=RGBColor(255, 255, 255))
text(s, 0.8, 3.1, 11.5, 1.0, ["Détection précoce de fuites d'air sur des pannes réelles (UCI MetroPT-3)"], size=22,
     color=RGBColor(0xDD, 0xE6, 0xF3))
text(s, 0.8, 4.6, 11.5, 1.2, ["Abderahmane Abderrahmane (22053) · Hafssatou Bilal (22067)",
                              "AML313 · Séries temporelles de capteurs IoT · Master SupNum — Groupe 5"], size=16,
     color=RGBColor(0xDD, 0xE6, 0xF3))

# 2 ─ Problème
n += 1; s = slide("Question métier et données", n)
text(s, 0.5, 1.3, 6.6, 5.5, [
    "- L'APU (unité de production d'air) alimente freins, suspension et portes.",
    "- Une fuite d'air non détectée immobilise le train en ligne.",
    "- Objectif : alerter AVANT la panne, dans une fenêtre utile pour l'atelier (≤ 7 jours).",
    "- Données : MetroPT-3, Porto, 01/02 → 01/09/2020, 7 capteurs analogiques + 8 binaires.",
    "- Vérité terrain : 4 fuites d'air documentées (18/04, 29/05, 05/06, 15/07).",
    "- Baseline imposée : résidu de prévision + seuil + persistance.",
    "- Métriques : rappel par événement, avance d'alerte, fausses alertes / mois."], size=17)
pic(s, FIG / "02_indicateurs_cycles.png", 7.2, 1.4, w=5.8)

# 3 ─ Diagnostic
n += 1; s = slide("Phase 1 · Diagnostic du jeu brut", n)
pic(s, FIG / "01_grille.png", 0.5, 1.3, w=7.4)
text(s, 8.1, 1.3, 4.8, 5.5, [
    "- 1 516 948 lignes : décimé à ~10 s (pas 1 Hz).",
    "- 0 doublon, 0 valeur manquante codée.",
    "- 331 coupures > 60 s (909 h) : rame éteinte → manquant NON aléatoire → pas d'imputation.",
    "- Régimes : arrêt 55 %, vide 30 %, charge 16 %.",
    "- Pannes #1 et #3 : capteurs figés/absents → il faut détecter en amont.",
    "- Hypothèse écrite avant modèle : une fuite accélère la chute de pression au repos."], size=16)

# 4 ─ Indicateurs causaux
n += 1; s = slide("Phase 2 · Un indicateur par cycle de compression, strictement causal", n)
ind = pd.DataFrame([
    ["durée, vitesse de charge", "cycle courant", "durée ↑"],
    ["repos avant le cycle", "fin du cycle PRÉCÉDENT", "↓"],
    ["chute de pression au repos", "cycle précédent → début", "↑↑"],
    ["rapport de service", "charge / (charge + repos)", "↑"],
    ["T° huile, courant", "cycle courant", "↑"],
    ["tendances", "médiane des 15 cycles passés", "dérive"],
], columns=["Indicateur", "Calculé avec", "Fuite"])
table(s, ind, 0.5, 1.4, 7.2, 3.6, size=14)
text(s, 8.0, 1.3, 4.9, 5.6, [
    "Corrigé par rapport à la v1 :",
    "- idle_sec utilisait le cycle SUIVANT + bfill() → fuite du futur.",
    "- alarme datée au début du cycle → datée à la FIN (instant de décision).",
    "Garanties :",
    "- aucune grandeur à travers une coupure ;",
    "- test automatique : tronquer les données à t ne change aucun cycle terminé avant t.",
    "- 10 751 cycles retenus (filtre physique journalisé)."], size=15)

# 5 ─ Protocole
n += 1; s = slide("Phase 3 · Validation chronologique avec gap", n)
blocks = [("Train\n01/02–31/03", 0.5, 4.2, RGBColor(0xD9, 0xEA, 0xD3)), ("gap 3 j", 4.75, 0.6, RGBColor(0xEE, 0xEE, 0xEE)),
          ("Validation\n04/04–10/05\n(panne #1)", 5.4, 2.6, RGBColor(0xFF, 0xF2, 0xCC)), ("gap 3 j", 8.05, 0.6, RGBColor(0xEE, 0xEE, 0xEE)),
          ("Test (1 seule fois)\n14/05–01/09\npannes #2 #3 #4", 8.7, 4.1, RGBColor(0xDA, 0xE8, 0xFC))]
for lab, x, w, col in blocks:
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.5), Inches(w), Inches(1.3))
    b.fill.solid(); b.fill.fore_color.rgb = col; b.line.color.rgb = RGBColor(0x99, 0x99, 0x99)
    b.text_frame.text = lab
    for p in b.text_frame.paragraphs:
        p.font.size = Pt(13 if w > 1 else 10); p.font.color.rgb = GREY
text(s, 0.5, 3.2, 12.3, 3.8, [
    "- Train : scaler, Ridge, Isolation Forest, ACP et seuils ajustés ici UNIQUEMENT (10 jours aberrants de mars exclus de la référence, règle calculée sur le train).",
    "- Gap 3 j > mémoire des indicateurs (15 cycles ≈ 8 h, EWMA, persistance).",
    "- Validation : choix du quantile q et de la persistance K. Règle : FA ≤ 2/mois → rappel max → réglage le plus sensible (coût asymétrique).",
    "- Évaluation PAR ÉVÉNEMENT : alarme utile seulement dans [début − 7 j, début[ ; pendant la panne = tardive.",
    "- Alarmes à < 24 h d'intervalle = 1 épisode ; IC 95 % Clopper-Pearson / Poisson ; comparaison à un détecteur aléatoire."], size=16)

# 6 ─ Modèles
n += 1; s = slide("Baseline puis modèles plus riches", n)
text(s, 0.5, 1.3, 6.1, 5.5, [
    "Baseline (imposée)",
    "- Ridge : contexte (heure, week-end) → chute de pression au repos.",
    "- Pas la T° d'huile : elle monte AVEC la fuite.",
    "- Résidu standardisé → EWMA causale (10 cycles).",
    "- Seuil q = 0,99 du train, persistance K = 1."], size=17, bold_first=True)
text(s, 6.9, 1.3, 6.0, 5.5, [
    "Modèles plus riches",
    "- Isolation Forest (200 arbres, graine 42), 12 indicateurs : q = 0,95, K = 6.",
    "- ACP 90 % de variance, score max(T², SPE) : q = 0,95, K = 6.",
    "- Même protocole, mêmes métriques."], size=17, bold_first=True)

# 7 ─ Résultats
n += 1; s = slide("Résultats sur le test (utilisé une seule fois)", n)
t = m[m.split == "test"].copy()
res = pd.DataFrame({
    "Détecteur": t.detecteur.str.replace(" (résidu Ridge + EWMA)", "", regex=False),
    "Détectées avant": t.n_detectees_avant.astype(str) + "/" + t.n_pannes.astype(str),
    "IC 95 % rappel": t.rappel_IC95.str.replace("[", "[", regex=False),
    "FA / mois [IC 95 %]": t.FA_par_mois.astype(str) + " " + t.FA_par_mois_IC95,
    "% cycles en alarme": (t.part_cycles_en_alarme * 100).round(1).astype(str) + " %",
    "Hasard (W=7 j)": t.rappel_detecteur_aleatoire,
})
table(s, res, 0.5, 1.4, 12.3, 1.8, size=14)
text(s, 0.5, 3.6, 12.3, 3.3, [
    "- 3/3 pannes du test signalées AVANT leur début par les trois détecteurs ; panne #1 (validation) manquée : capteurs figés, aucune dérive préalable.",
    "- Panne #2 : consommation d'air au repos ×2 dès le 17/05 → point P 12 jours avant F (avance plafonnée par W = 7 j).",
    "- Mais 5 à 7 épisodes de fausse alerte / mois : dérive durable de la consommation à partir de mi-mai.",
    "- Baseline = meilleur compromis (14 FA, 15,7 % des cycles en alarme)."], size=16)

# 8 ─ Frise
n += 1; s = slide("Frise des pannes et alarmes (lien courbe P-F)", n)
pic(s, FIG / "03_frise_detections.png", 0.4, 1.15, h=5.8)
pic(s, FIG / "04_zoom_pannes.png", 8.3, 1.15, h=5.8)

# 9 ─ Ablation + sensibilité
n += 1; s = slide("Ablation et sensibilité à la fenêtre utile", n)
a = abl[["variante", "n_variables", "test_detectees", "test_FA_mois"]].copy()
a.columns = ["Variante IF", "Nb var.", "Test : détectées", "Test : FA/mois"]
table(s, a, 0.5, 1.3, 6.4, 3.8, size=13)
sb = sens[sens.detecteur.str.startswith("Baseline")][["fenetre_j", "detectees", "rappel_aleatoire"]]
sb.columns = ["W (jours)", "Baseline : détectées /3", "Hasard"]
table(s, sb, 7.3, 1.3, 5.5, 2.6, size=13)
text(s, 0.5, 5.4, 12.3, 1.6, [
    "- 3 indicateurs « repos / fuite » suffisent : 3/3 et moins de FA que le modèle complet → l'hypothèse physique est confirmée.",
    "- Sans tendances : FA ÷ 4 mais panne #2 manquée.  Gain sur le hasard net à 1–3 j, faible à 7 j."], size=15)

# 10 ─ Coût
n += 1; s = slide("Coût d'une fausse alerte face à une panne en service", n)
c = couts.copy(); c["strategie"] = c.strategie.str.replace(" (résidu Ridge + EWMA)", "", regex=False)
c.columns = ["Stratégie (test)", "Fausses alertes", "Pannes ratées", "Coût total (€)"]
c["Coût total (€)"] = c["Coût total (€)"].map(lambda v: f"{v:,.0f}".replace(",", " "))
table(s, c, 0.5, 1.4, 8.0, 2.4, size=14)
text(s, 8.8, 1.3, 4.2, 5.5, [
    "Hypothèses : FA = inspection 150 € ; alerte vraie = réparation planifiée 200 € ; panne en ligne ≈ 20 000 €.",
    "- Ratio ≈ 130 : une panne évitée paie ~130 FA.",
    "- Limite réelle = fatigue d'alarme (> 1 FA / semaine).",
    "- Recommandation : baseline, recalibrée après chaque maintenance."], size=15)

# 11 ─ Limites
n += 1; s = slide("Limites et suites", n)
text(s, 0.5, 1.3, 12.3, 5.6, [
    "- 1 panne en validation, 3 en test : IC larges ([0,29 ; 1]) → résultats indicatifs.",
    "- Non-stationnarité (saison, charge, fuite résiduelle ?) : principale source de fausses alertes. Pistes NON testées sur le test : référence glissante décalée, recalibrage après maintenance, température extérieure.",
    "- Validation peu informative (panne #1 sans signature) : seuil surtout guidé par le budget FA.",
    "- W = 7 j est un choix métier ; l'avance mesurée est plafonnée par W.",
    "- Données décimées à 10 s ; coûts à valider avec l'exploitant ; signaux LPS/MPG non utilisés."], size=17)

# 12 ─ Reproductibilité
n += 1; s = slide("Reproductibilité — une seule commande", n)
text(s, 0.5, 1.4, 12.3, 1.0, ["bash run_all.sh"], size=30, color=NAVY)
text(s, 0.5, 2.4, 12.3, 4.5, [
    "- venv figé (requirements.txt), téléchargement UCI + vérification SHA-256, graines fixées (42).",
    "- src/ : features.py (causal), detectors.py, evaluation.py (métriques par événement), run_pipeline.py.",
    "- Résultats : results/*.csv, resultats.json, pipeline.log ; figures dans results/figures/.",
    "- Notebook ré-exécuté de bout en bout ; rapport (5 p.) dans rapport/.",
    "",
    "Merci — questions ?"], size=18)

out = Path(__file__).resolve().parent / "soutenance.pptx"
prs.save(out)
print("écrit :", out)
