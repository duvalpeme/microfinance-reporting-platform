#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exécution des contrôles qualité (catalogue : quality/rules.yml) sur la couche BRONZE.

Écrit dans DuckDB, schéma `quality` :
  - quality.violations : une ligne par (règle, clé en infraction) pour l'exécution courante.
                         C'est cette table qui pilote la quarantaine et les marqueurs du silver.
  - quality.resultats  : une ligne par règle et par exécution (historique conservé).
  - quality.gate       : décision de publication (OUVERTE / BLOQUEE) pour l'exécution courante.

Usage (depuis la racine du projet) :
    python quality/run_checks.py
    python quality/run_checks.py --strict     # code de sortie 2 si la publication est bloquée
"""
import argparse
import sys
import time
from datetime import datetime

import duckdb
import yaml

TRAITEMENT = {"quarantaine": "TRAITE", "dedoublonnage": "TRAITE", "correction": "TRAITE", "signalement": "ALERTE"}


def main():
    ap = argparse.ArgumentParser(description="Contrôles qualité sur la couche bronze")
    ap.add_argument("--db", default="data/warehouse/imf.duckdb")
    ap.add_argument("--rules", default="quality/rules.yml")
    ap.add_argument("--strict", action="store_true", help="échoue (code 2) si la publication est bloquée")
    args = ap.parse_args()

    rules = yaml.safe_load(open(args.rules, encoding="utf-8"))["rules"]
    con = duckdb.connect(args.db)
    try:
        arrete = con.execute("SELECT valeur FROM bronze._meta WHERE cle = 'date_arrete'").fetchone()[0]
        run_id = con.execute("SELECT valeur FROM bronze._meta WHERE cle = 'run_id'").fetchone()[0]
    except duckdb.Error:
        sys.exit("Couche bronze absente : lance d'abord python pipeline/bronze/ingest.py")

    con.execute("CREATE SCHEMA IF NOT EXISTS quality")
    con.execute("DROP TABLE IF EXISTS quality.violations")
    con.execute("""
        CREATE TABLE quality.violations (
            run_id VARCHAR, regle_id VARCHAR, table_source VARCHAR, cle VARCHAR,
            severite VARCHAR, action VARCHAR, anomaly_type VARCHAR, bloque_publication BOOLEAN,
            motif VARCHAR, detecte_le TIMESTAMP)
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS quality.resultats (
            run_id VARCHAR, regle_id VARCHAR, table_source VARCHAR, dimension VARCHAR,
            severite VARCHAR, action VARCHAR, bloque_publication BOOLEAN,
            nb_violations BIGINT, statut VARCHAR, duree_ms BIGINT, executee_le TIMESTAMP)
    """)
    con.execute("DELETE FROM quality.resultats WHERE run_id = ?", [run_id])

    now = datetime.now().replace(microsecond=0)
    print(f"Contrôles qualité - run {run_id} - arrêté {arrete}\n")
    print(f"{'Règle':<28}{'Violations':>11}  {'Statut':<9} Action")
    print("-" * 72)

    bloquantes = []
    for r in rules:
        sql = r["sql"].replace("{{ARRETE}}", arrete)
        t0 = time.time()
        n = con.execute(f"SELECT count(*) FROM ({sql}) q").fetchone()[0]
        con.execute(f"""
            INSERT INTO quality.violations
            SELECT ?, ?, ?, cle, ?, ?, ?, ?, ?, ? FROM ({sql}) q
        """, [run_id, r["id"], r["table"], r["severite"], r["action"], r["anomaly_type"],
              bool(r["bloque_publication"]), " ".join(r["description"].split()), now])
        ms = int((time.time() - t0) * 1000)

        if n == 0:
            statut = "OK"
        elif r["bloque_publication"]:
            statut = "BLOQUANT"
            bloquantes.append(r["id"])
        else:
            statut = TRAITEMENT[r["action"]]
        con.execute("INSERT INTO quality.resultats VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [run_id, r["id"], r["table"], r["dimension"], r["severite"], r["action"],
                     bool(r["bloque_publication"]), n, statut, ms, now])
        print(f"{r['id']:<28}{n:>11,}  {statut:<9} {r['action']}")

    con.execute("DROP TABLE IF EXISTS quality.gate")
    gate = "BLOQUEE" if bloquantes else "OUVERTE"
    con.execute("CREATE TABLE quality.gate (run_id VARCHAR, decision VARCHAR, regles_bloquantes VARCHAR, evaluee_le TIMESTAMP)")
    con.execute("INSERT INTO quality.gate VALUES (?,?,?,?)", [run_id, gate, ", ".join(bloquantes), now])

    total = con.execute("SELECT count(*) FROM quality.violations").fetchone()[0]
    print("-" * 72)
    print(f"{total:,} violations enregistrées dans quality.violations")
    if bloquantes:
        print(f"PUBLICATION DES ÉTATS : BLOQUÉE par {len(bloquantes)} règle(s) critique(s) : {', '.join(bloquantes)}")
    else:
        print("PUBLICATION DES ÉTATS : OUVERTE")
    con.close()
    if args.strict and bloquantes:
        sys.exit(2)


if __name__ == "__main__":
    main()
