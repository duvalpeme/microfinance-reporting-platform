#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export des tables gold (et des résultats qualité) vers des fichiers lisibles par Power BI Desktop.

Format par défaut : Parquet. Power BI le lit nativement (Obtenir des données > Parquet) et il conserve
les types (dates, nombres) : pas de souci de séparateur décimal ou de paramètres régionaux, fréquent avec
les CSV sur un poste en français. Un export CSV reste possible avec --format csv.

Fichiers produits (dossier exports/powerbi par défaut) :
    dim_agence              référentiel des agences
    par_agence              qualité du portefeuille par agence (sans la ligne TOTAL)
    synthese_portefeuille   la ligne TOTAL : encours, PAR 1/30/90, provisions
    encours_pret            une ligne par prêt (encours, retard, tranche, provision)
    concentration           répartition par agence, produit, secteur, type de client
    grands_engagements      20 plus gros engagements
    rapprochement           rapprochement portefeuille / comptabilité par agence et date
    rapprochement_total     rapprochement au niveau institution
    statut_publication      décision de publication des états et ses motifs
    taux_provision          barème de provisionnement (illustratif)
    regles_qualite          les 14 règles de contrôle et leur résultat à la dernière exécution
    detection_anomalies     taux de détection par type d'anomalie injectée
    meta                    date d'arrêté, exécution, date de l'export

Usage (depuis la racine du projet) :
    python pipeline/export_powerbi.py
    python pipeline/export_powerbi.py --format csv
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

import duckdb
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABLES = {
    "dim_agence": "SELECT code_agence, nom_agence, region FROM silver.silver_agences",
    "par_agence": "SELECT * FROM gold.gold_par_agence WHERE code_agence <> 'TOTAL' ORDER BY code_agence",
    "synthese_portefeuille": "SELECT * FROM gold.gold_par_agence WHERE code_agence = 'TOTAL'",
    "encours_pret": "SELECT * FROM gold.gold_encours_pret",
    "concentration": "SELECT * FROM gold.gold_concentration",
    "grands_engagements": "SELECT * FROM gold.gold_grands_engagements ORDER BY rang",
    "rapprochement": "SELECT * FROM gold.gold_rapprochement ORDER BY date_arrete DESC, code_agence",
    "rapprochement_total": "SELECT * FROM gold.gold_rapprochement_total ORDER BY date_arrete DESC",
    "statut_publication": "SELECT * FROM gold.gold_statut_publication",
    "taux_provision": "SELECT * FROM gold.gold_taux_provision ORDER BY ordre",
}


def write_table(df, path, fmt):
    con = duckdb.connect()
    con.register("t", df)
    options = "FORMAT PARQUET" if fmt == "parquet" else "FORMAT CSV, HEADER"
    con.execute(f"COPY t TO '{path.replace(chr(92), '/')}' ({options})")
    con.close()


def main():
    ap = argparse.ArgumentParser(description="Export des tables gold pour Power BI")
    ap.add_argument("--db", default="data/warehouse/imf.duckdb")
    ap.add_argument("--out", default="exports/powerbi")
    ap.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    args = ap.parse_args()
    ext = args.format

    os.makedirs(args.out, exist_ok=True)
    try:
        con = duckdb.connect(args.db, read_only=True)
        con.execute("SELECT 1 FROM gold.gold_encours_pret LIMIT 1")
    except duckdb.Error:
        sys.exit("Couche gold introuvable : lance d'abord python pipeline/run_pipeline.py")

    print(f"Export Power BI ({ext}) vers {os.path.abspath(args.out)}\n")
    fichiers = []

    def sortie(nom, df):
        # Types propres pour Power BI : compteurs entiers, colonnes date_* en vrais dates
        for col in df.columns:
            if col.startswith("nb_"):
                df[col] = df[col].astype("Int64")
            elif col.startswith("date_") and len(df):
                df[col] = pd.to_datetime(df[col]).dt.date
        chemin = os.path.abspath(os.path.join(args.out, f"{nom}.{ext}"))
        write_table(df, chemin, ext)
        fichiers.append(chemin)
        print(f"  {nom:<24} {len(df):>9,} lignes   {os.path.getsize(chemin) / 1024:>9,.0f} Ko".replace(",", " "))

    for nom, sql in TABLES.items():
        sortie(nom, con.execute(sql).df())

    # Règles qualité : métadonnées du catalogue + résultat de la dernière exécution
    run_id = con.execute("SELECT valeur FROM bronze._meta WHERE cle = 'run_id'").fetchone()[0]
    arrete = con.execute("SELECT valeur FROM bronze._meta WHERE cle = 'date_arrete'").fetchone()[0]
    res = con.execute("""SELECT regle_id, nb_violations, statut FROM quality.resultats WHERE run_id = ?""", [run_id]).df()
    regles = yaml.safe_load(open(os.path.join(ROOT, "quality", "rules.yml"), encoding="utf-8"))["rules"]
    meta_regles = pd.DataFrame([{
        "regle_id": r["id"], "table_source": r["table"], "dimension": r["dimension"], "severite": r["severite"],
        "action": r["action"], "bloque_publication": bool(r["bloque_publication"]),
        "proprietaire": r["proprietaire"], "description": " ".join(r["description"].split()),
    } for r in regles])
    sortie("regles_qualite", meta_regles.merge(res, on="regle_id", how="left").sort_values("regle_id"))

    # Taux de détection : réutilise l'évaluation du projet
    chemin_det = os.path.abspath(os.path.join(args.out, f"detection_anomalies.{ext}"))
    code = subprocess.call([sys.executable, os.path.join(ROOT, "quality", "evaluate_detection.py"),
                            "--db", args.db, "--out", chemin_det],
                           cwd=os.getcwd(), stdout=subprocess.DEVNULL)
    if code == 0 and os.path.exists(chemin_det):
        fichiers.append(chemin_det)
        n = duckdb.connect().execute(
            f"SELECT count(*) FROM {'read_parquet' if ext == 'parquet' else 'read_csv'}('{chemin_det.replace(chr(92), '/')}')").fetchone()[0]
        print(f"  {'detection_anomalies':<24} {n:>9,} lignes   {os.path.getsize(chemin_det) / 1024:>9,.0f} Ko".replace(",", " "))
    else:
        print("  detection_anomalies      non produit (fichier de corrigé introuvable : data/raw/anomalies_injectees.csv)")

    sortie("meta", pd.DataFrame([{"date_arrete": arrete, "run_id": run_id,
                                  "exporte_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]))
    con.close()
    print(f"\n{len(fichiers)} fichiers écrits. Dans Power BI : Obtenir des données > "
          f"{'Parquet' if ext == 'parquet' else 'Texte/CSV'}.")


if __name__ == "__main__":
    main()
