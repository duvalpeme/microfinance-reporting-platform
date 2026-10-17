#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aperçu lisible de la couche gold : décision de publication, qualité du portefeuille,
rapprochement portefeuille / comptabilité, concentration.

Usage (depuis la racine du projet) :
    python pipeline/apercu_gold.py
"""
import argparse

import duckdb


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2%}" if abs(v) < 1.5 else f"{v:,.0f}".replace(",", " ")
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    if hasattr(v, "as_tuple"):  # Decimal
        return f"{int(v):,}".replace(",", " ")
    return str(v)


def show(con, titre, sql):
    res = con.execute(sql)
    cols = [d[0] for d in res.description]
    rows = [[fmt(v) for v in r] for r in res.fetchall()]
    larg = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print(f"\n{titre}\n" + "-" * (sum(larg) + 2 * len(cols)))
    print("  ".join(c.ljust(larg[i]) for i, c in enumerate(cols)))
    for r in rows:
        print("  ".join(v.rjust(larg[i]) for i, v in enumerate(r)))


def main():
    ap = argparse.ArgumentParser(description="Aperçu de la couche gold")
    ap.add_argument("--db", default="data/warehouse/imf.duckdb")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)

    show(con, "DÉCISION DE PUBLICATION DES ÉTATS",
         "SELECT date_arrete, decision, motifs FROM gold.gold_statut_publication")
    show(con, "QUALITÉ DU PORTEFEUILLE (à l'arrêté)", """
        SELECT code_agence AS agence, nb_prets_actifs AS prets, encours_total AS encours, par30, par90,
               taux_provisionnement AS prov, par30_hors_incertain AS par30_hors_incert
        FROM gold.gold_par_agence ORDER BY code_agence = 'TOTAL', code_agence""")
    show(con, "RAPPROCHEMENT PORTEFEUILLE / COMPTABILITÉ - au niveau institution", """
        SELECT date_arrete, ecart_brut, effet_quarantaine_total AS effet_quarantaine, compte_attente,
               ecart_non_explique AS non_explique, statut
        FROM gold.gold_rapprochement_total ORDER BY date_arrete DESC""")
    show(con, "RAPPROCHEMENT - agences à examiner", """
        SELECT date_arrete, code_agence AS agence, ecart_apres_quarantaine AS ecart, seuil_tolerance AS seuil,
               incertitude_dates AS incertitude, statut
        FROM gold.gold_rapprochement WHERE statut NOT IN ('CONFORME', 'A_REPARTIR')
        ORDER BY date_arrete DESC, code_agence""")
    show(con, "CONCENTRATION PAR PRODUIT", """
        SELECT segment AS produit, nb_prets AS prets, encours, part_encours AS part, par30
        FROM gold.gold_concentration WHERE dimension = 'PRODUIT' ORDER BY encours DESC""")
    show(con, "CONCENTRATION PAR SECTEUR", """
        SELECT segment AS secteur, nb_prets AS prets, encours, part_encours AS part, par30
        FROM gold.gold_concentration WHERE dimension = 'SECTEUR' ORDER BY encours DESC""")
    show(con, "5 PLUS GRANDS ENGAGEMENTS", """
        SELECT rang, client, code_agence AS agence, encours, part_encours_total AS part_encours,
               part_fonds_propres AS part_fonds_propres
        FROM gold.gold_grands_engagements ORDER BY rang LIMIT 5""")
    con.close()


if __name__ == "__main__":
    main()
