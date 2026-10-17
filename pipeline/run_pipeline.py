#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrateur : exécute la chaîne complète dans l'ordre.

    1. bronze   : ingestion brute des CSV dans DuckDB
    2. quality  : contrôles sur le bronze (règles de quality/rules.yml)
    3. silver   : modèles dbt (nettoyage, dédoublonnage, quarantaine)
    4. tests    : tests dbt sur le silver
    5. rapport  : taux de détection des anomalies injectées
    6. export   : tables gold au format Parquet pour Power BI (exports/powerbi)

Usage (depuis la racine du projet) :
    python pipeline/run_pipeline.py
    python pipeline/run_pipeline.py --generate        # régénère d'abord les données
    python pipeline/run_pipeline.py --generate --seed 7 --taux-anomalies 0
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBT_DIR = os.path.join("pipeline", "dbt_project")


def run(titre, cmd):
    print(f"\n{'=' * 78}\n{titre}\n{'=' * 78}", flush=True)
    t0 = time.time()
    code = subprocess.call(cmd, cwd=ROOT)
    if code != 0:
        sys.exit(f"\nÉchec à l'étape : {titre} (code {code})")
    print(f"-- terminé en {time.time() - t0:.1f}s", flush=True)


def dbt(*args):
    code = (f"import sys; from dbt.cli.main import dbtRunner; "
            f"r = dbtRunner().invoke({list(args) + ['--project-dir', DBT_DIR, '--profiles-dir', DBT_DIR]!r}); "
            f"sys.exit(0 if r.success else 1)")
    return [sys.executable, "-c", code]


def main():
    ap = argparse.ArgumentParser(description="Pipeline complet bronze -> silver + qualité")
    ap.add_argument("--generate", action="store_true", help="régénère d'abord les données synthétiques")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--taux-anomalies", type=float, default=1.0)
    args = ap.parse_args()

    profil = os.path.join(ROOT, DBT_DIR, "profiles.yml")
    if not os.path.exists(profil):
        shutil.copy(profil + ".example", profil)
        print("profiles.yml créé à partir de profiles.yml.example")

    t0 = time.time()
    if args.generate:
        run("0. Génération des données synthétiques",
            [sys.executable, "data/generator/generate_data.py", "--out", "data/raw",
             "--seed", str(args.seed), "--taux-anomalies", str(args.taux_anomalies)])
    run("1. Bronze : ingestion", [sys.executable, "pipeline/bronze/ingest.py"])
    run("2. Qualité : contrôles sur le bronze", [sys.executable, "quality/run_checks.py"])
    run("3. Silver : modèles dbt", dbt("run"))
    run("4. Silver : tests dbt", dbt("test"))
    run("5. Rapport de détection", [sys.executable, "quality/evaluate_detection.py"])
    run("6. Export pour Power BI", [sys.executable, "pipeline/export_powerbi.py"])
    print(f"\nPipeline terminé en {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
