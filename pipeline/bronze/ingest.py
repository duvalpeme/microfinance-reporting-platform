#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Couche BRONZE - ingestion brute des exports CSV dans DuckDB.

Principes :
  - Les données sont chargées TELLES QUELLES : toutes les colonnes en texte (all_varchar),
    pour ne jamais perdre une valeur sale (date mal formée, montant négatif, code erroné).
    Le typage se fait en silver.
  - Chaque table reçoit deux colonnes de traçabilité : _source_file et _loaded_at.
  - Chaque exécution est journalisée dans bronze._ingestion_log (fichier, lignes, SHA-256).
  - Le fichier de vérité des anomalies (anomalies_injectees.csv) n'est PAS chargé :
    il sert uniquement à évaluer la détection (quality/evaluate_detection.py).

Usage (depuis la racine du projet) :
    python pipeline/bronze/ingest.py
    python pipeline/bronze/ingest.py --raw data/raw --db data/warehouse/imf.duckdb
"""
import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime

import duckdb

TABLES = [
    "agences", "agents", "produits", "plan_comptable",
    "clients", "prets", "echeanciers", "remboursements",
    "epargne_comptes", "epargne_mouvements", "balance_comptable",
]


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Ingestion bronze (CSV -> DuckDB)")
    ap.add_argument("--raw", default="data/raw", help="dossier des CSV sources")
    ap.add_argument("--db", default="data/warehouse/imf.duckdb", help="base DuckDB")
    args = ap.parse_args()

    missing = [t for t in TABLES if not os.path.exists(os.path.join(args.raw, f"{t}.csv"))]
    if missing:
        sys.exit(f"Fichiers manquants dans {args.raw} : {', '.join(missing)}\n"
                 f"Lance d'abord : python data/generator/generate_data.py --out {args.raw}")

    manifest_path = os.path.join(args.raw, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8")) if os.path.exists(manifest_path) else {}
    date_arrete = manifest.get("date_arrete")
    if not date_arrete:
        sys.exit("manifest.json introuvable ou sans date_arrete : relance le générateur.")

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    con = duckdb.connect(args.db)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    loaded_at = datetime.now().replace(microsecond=0)

    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("""
        CREATE TABLE IF NOT EXISTS bronze._ingestion_log (
            run_id VARCHAR, table_name VARCHAR, source_file VARCHAR,
            nb_lignes BIGINT, taille_octets BIGINT, sha256 VARCHAR, loaded_at TIMESTAMP)
    """)

    print(f"Ingestion bronze - run {run_id}")
    for t in TABLES:
        path = os.path.abspath(os.path.join(args.raw, f"{t}.csv")).replace("\\", "/")
        con.execute(f"DROP TABLE IF EXISTS bronze.{t}")
        con.execute(f"""
            CREATE TABLE bronze.{t} AS
            SELECT *, '{t}.csv' AS _source_file, TIMESTAMP '{loaded_at}' AS _loaded_at
            FROM read_csv('{path}', header = true, all_varchar = true)
        """)
        n = con.execute(f"SELECT count(*) FROM bronze.{t}").fetchone()[0]
        con.execute("INSERT INTO bronze._ingestion_log VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [run_id, t, f"{t}.csv", n, os.path.getsize(path), sha256(path), loaded_at])
        print(f"  bronze.{t:<22} {n:>9,} lignes")

    # Métadonnées de l'arrêté : source unique de vérité pour qualité et silver
    con.execute("DROP TABLE IF EXISTS bronze._meta")
    con.execute("CREATE TABLE bronze._meta (cle VARCHAR, valeur VARCHAR)")
    con.execute("INSERT INTO bronze._meta VALUES ('date_arrete', ?), ('run_id', ?), ('source_dir', ?)",
                [date_arrete, run_id, os.path.abspath(args.raw)])
    con.close()
    print(f"OK - date d'arrêté : {date_arrete} | base : {args.db}")


if __name__ == "__main__":
    main()
