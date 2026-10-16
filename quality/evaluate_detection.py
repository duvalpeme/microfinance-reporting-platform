#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure du taux de détection des contrôles qualité.

Compare, type d'anomalie par type d'anomalie :
  - le "corrigé"   : data/raw/anomalies_injectees.csv (écrit par le générateur)
  - les détections : quality.violations (écrit par quality/run_checks.py)

Indicateurs :
  - rappel    = anomalies injectées retrouvées / anomalies injectées
  - précision = détections correctes / détections totales de la règle
  - faux positifs = détections qui ne correspondent à aucune anomalie injectée

Sur un jeu généré avec --taux-anomalies 0, le fichier de corrigé est vide :
tout ce qui est détecté est alors un faux positif (cible : 0).

Usage (depuis la racine du projet) :
    python quality/evaluate_detection.py
    python quality/evaluate_detection.py --md docs/rapport_detection.md
"""
import argparse
import os
import sys

import duckdb
import pandas as pd
import yaml


def main():
    ap = argparse.ArgumentParser(description="Évaluation de la détection des anomalies")
    ap.add_argument("--db", default="data/warehouse/imf.duckdb")
    ap.add_argument("--truth", default="data/raw/anomalies_injectees.csv")
    ap.add_argument("--rules", default="quality/rules.yml")
    ap.add_argument("--md", default=None, help="écrit aussi le rapport au format Markdown")
    args = ap.parse_args()

    if not os.path.exists(args.truth):
        sys.exit(f"Corrigé introuvable : {args.truth}")
    truth = pd.read_csv(args.truth, dtype=str)
    con = duckdb.connect(args.db, read_only=True)
    viol = con.execute('SELECT table_source AS "table", cle, anomaly_type, regle_id FROM quality.violations').df()
    con.close()

    # Types d'anomalies qu'une règle du catalogue sait détecter
    couverts = {r["anomaly_type"] for r in yaml.safe_load(open(args.rules, encoding="utf-8"))["rules"]}
    inj_types = set(truth["type_anomalie"])
    hors_perimetre = sorted(inj_types - couverts)

    def cles(df, t, col):
        return set(map(tuple, df.loc[df[col] == t, ["table", "cle"]].values))

    rows = []
    for t in sorted((inj_types & couverts) | set(viol["anomaly_type"])):
        inj, det = cles(truth, t, "type_anomalie"), cles(viol, t, "anomaly_type")
        tp = len(inj & det)
        regles = ", ".join(sorted(viol.loc[viol["anomaly_type"] == t, "regle_id"].unique())) or "-"
        rows.append({"type_anomalie": t, "regle": regles, "injectees": len(inj), "detectees": len(det),
                     "manquees": len(inj - det), "faux_positifs": len(det - inj),
                     "rappel": tp / len(inj) if inj else None, "precision": tp / len(det) if det else None,
                     "_manquees": sorted(inj - det)})
    res = pd.DataFrame(rows)

    def pct(x):
        return "n/a" if x is None or pd.isna(x) else f"{x:.1%}"

    if res.empty:
        print("Aucune anomalie injectée et aucune violation détectée : 0 faux positif.")
        return

    inj_tot = int(res["injectees"].sum())
    det_tot = int(res["detectees"].sum())
    fp_tot = int(res["faux_positifs"].sum())
    tp_tot = det_tot - fp_tot
    rappel_glob = tp_tot / inj_tot if inj_tot else None
    prec_glob = tp_tot / det_tot if det_tot else None

    lines = [f"{'Type d anomalie':<30}{'Injectées':>10}{'Détectées':>10}{'Manquées':>9}{'Faux+':>7}{'Rappel':>9}{'Précision':>10}",
             "-" * 85]
    for _, r in res.iterrows():
        lines.append(f"{r['type_anomalie']:<30}{r['injectees']:>10}{r['detectees']:>10}{r['manquees']:>9}"
                     f"{r['faux_positifs']:>7}{pct(r['rappel']):>9}{pct(r['precision']):>10}")
    lines += ["-" * 85,
              f"{'TOTAL (types couverts)':<30}{inj_tot:>10}{det_tot:>10}{inj_tot - tp_tot:>9}{fp_tot:>7}"
              f"{pct(rappel_glob):>9}{pct(prec_glob):>10}"]
    print("\n".join(lines))
    if hors_perimetre:
        print("\nTypes injectés sans règle de détection (hors périmètre de cette étape) : " + ", ".join(hors_perimetre))

    manquees = [(r["type_anomalie"], tb, cle) for _, r in res.iterrows() for tb, cle in r["_manquees"]]
    if manquees:
        print(f"\nAnomalies manquées ({len(manquees)}) - extrait :")
        for t, tb, cle in manquees[:10]:
            print(f"  {t:<28} {tb}:{cle}")

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("# Rapport de détection des anomalies\n\n")
            f.write("| Type d'anomalie | Règle | Injectées | Détectées | Manquées | Faux positifs | Rappel | Précision |\n")
            f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
            for _, r in res.iterrows():
                f.write(f"| {r['type_anomalie']} | {r['regle']} | {r['injectees']} | {r['detectees']} | {r['manquees']} | "
                        f"{r['faux_positifs']} | {pct(r['rappel'])} | {pct(r['precision'])} |\n")
            f.write(f"| **Total (types couverts)** | | **{inj_tot}** | **{det_tot}** | **{inj_tot - tp_tot}** | "
                    f"**{fp_tot}** | **{pct(rappel_glob)}** | **{pct(prec_glob)}** |\n")
            if hors_perimetre:
                f.write("\nTypes injectés sans règle (hors périmètre de cette étape) : " + ", ".join(hors_perimetre) + ".\n")
        print(f"\nRapport écrit : {args.md}")


if __name__ == "__main__":
    main()
