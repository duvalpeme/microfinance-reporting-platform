#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur de données synthétiques - Institution de microfinance fictive (zone CEMAC)
======================================================================================

Projet n°1 : plateforme de reporting réglementaire pour une IMF.
Ce script produit les fichiers SOURCES (couche "raw"/bronze) tels qu'ils sortiraient
d'un logiciel de gestion de microfinance, avec des défauts de qualité injectés
volontairement et tracés dans `anomalies_injectees.csv` (le "corrigé" de tes contrôles).

Tout est fictif : aucune donnée réelle, aucun client réel.

Hypothèses de modélisation (à documenter dans ton README) :
  - L'historique démarre à --debut (mise en production fictive du SI) : le portefeuille
    se construit à partir de zéro, sans soldes d'ouverture.
  - Échéancier mensuel, capital constant + intérêts sur capital restant dû.
  - Profils de remboursement : bon payeur, retardataire, paiement partiel avec
    complément tardif, défaillant (arrêt de paiement à partir d'une échéance).
  - Le plan comptable est SIMPLIFIÉ et FICTIF : à remplacer par le plan comptable
    réglementaire applicable à ta catégorie d'IMF.
  - Les taux de provisionnement par tranche de retard sont ILLUSTRATIFS.
  - La balance comptable est équilibrée par construction (actif = passif) et cohérente
    avec le portefeuille, sauf les écarts de rapprochement injectés volontairement.

Usage :
    pip install pandas numpy
    python generate_data.py --out data/raw
    python generate_data.py --clients 5000 --agences 8 --par30-cible 0.09 --seed 7
    python generate_data.py --taux-anomalies 0      # jeu propre, sans défauts injectés
"""
import argparse
import json
import os
import unicodedata

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Référentiels fictifs
# --------------------------------------------------------------------------------------
AGENCES = [
    ("Douala Akwa", "Littoral"), ("Yaoundé Centre", "Centre"), ("Bafoussam", "Ouest"),
    ("Garoua", "Nord"), ("Douala Bonabéri", "Littoral"), ("Yaoundé Mvog-Ada", "Centre"),
    ("Maroua", "Extrême-Nord"), ("Bertoua", "Est"), ("Ebolowa", "Sud"),
    ("Ngaoundéré", "Adamaoua"), ("Bamenda", "Nord-Ouest"), ("Dschang", "Ouest"),
    ("Kribi", "Sud"), ("Edéa", "Littoral"), ("Buea", "Sud-Ouest"),
]

# code, libellé, type_client, taux annuel, durées possibles (mois),
# montant médian, min, max, multiplicateur de risque
PRODUITS = [
    ("MICRO_COMMERCE", "Micro-crédit commerce", "INDIVIDUEL", 0.24, [6, 9, 12], 350_000, 50_000, 3_000_000, 1.00),
    ("CREDIT_GROUPE", "Crédit solidaire de groupe", "GROUPE", 0.22, [6, 8, 10, 12], 600_000, 200_000, 3_000_000, 0.80),
    ("AGRI", "Crédit agricole de campagne", "INDIVIDUEL", 0.20, [6, 9, 12], 500_000, 80_000, 4_000_000, 1.40),
    ("EQUIPEMENT", "Crédit équipement", "INDIVIDUEL", 0.18, [12, 18, 24], 1_200_000, 300_000, 8_000_000, 1.10),
    ("PME", "Crédit PME", "INDIVIDUEL", 0.16, [18, 24, 36], 4_000_000, 1_000_000, 25_000_000, 1.20),
    ("CONSO_URGENCE", "Crédit consommation/urgence", "INDIVIDUEL", 0.30, [3, 6], 120_000, 30_000, 500_000, 1.30),
]
PRODUIT_POIDS = [0.32, 0.18, 0.15, 0.12, 0.05, 0.18]

SECTEURS = ["COMMERCE", "AGRICULTURE", "ELEVAGE", "ARTISANAT", "TRANSPORT", "SERVICES", "TRANSFORMATION"]
SECTEUR_POIDS = [0.36, 0.22, 0.08, 0.10, 0.08, 0.10, 0.06]
SECTEUR_RISQUE = {"COMMERCE": 1.0, "AGRICULTURE": 1.3, "ELEVAGE": 1.1, "ARTISANAT": 0.95,
                  "TRANSPORT": 1.15, "SERVICES": 0.9, "TRANSFORMATION": 0.9}

PRENOMS_F = ["Marie", "Joséphine", "Aminatou", "Brigitte", "Chantal", "Estelle", "Nadège", "Clarisse",
             "Solange", "Fatimatou", "Mireille", "Sandrine", "Rosine", "Berthe", "Odette", "Pauline",
             "Hadjara", "Esther", "Carine", "Yvette"]
PRENOMS_M = ["Jean", "Paul", "Emmanuel", "Ibrahim", "Serge", "Alain", "Patrice", "Blaise", "Moussa",
             "Thierry", "Hervé", "Roger", "Désiré", "Aristide", "Boris", "Cyrille", "Gaston",
             "Mohamadou", "Parfait", "Valentin"]
NOMS = ["Mbarga", "Nkomo", "Tchamba", "Fotso", "Kamga", "Ngono", "Essomba", "Abanda", "Mvondo", "Tagne",
        "Ndongo", "Njoya", "Biyik", "Owona", "Ateba", "Djoumessi", "Kenfack", "Ngassa", "Tchoumi",
        "Mballa", "Bello", "Hamadou", "Abdoulaye", "Nana", "Talla", "Kouam", "Simo", "Eboa", "Etoundi", "Manga"]
GROUPES_PREFIXES = ["GIC", "Groupe", "Tontine", "Association"]
GROUPES_MOTS = ["Espoir", "Solidarité", "Entraide", "Avenir", "Unité", "Progrès", "Courage", "Réussite",
                "Femmes Actives", "Les Battantes", "Union", "Persévérance"]

# Plan comptable simplifié FICTIF
PLAN_COMPTABLE = [
    ("1010", "CAISSE", "Caisse", "ACTIF"),
    ("1020", "BANQUE", "Banques et correspondants", "ACTIF"),
    ("2010", "CRD_SAINS", "Crédits sains (retard <= 30 jours)", "ACTIF"),
    ("2020", "CRD_DOUTEUX", "Crédits en souffrance (retard 31-90 jours)", "ACTIF"),
    ("2030", "CRD_LITIGIEUX", "Crédits litigieux (retard > 90 jours)", "ACTIF"),
    ("2910", "PROVISIONS", "Provisions sur crédits (solde négatif)", "ACTIF"),
    ("4010", "IMMOBILISATIONS", "Immobilisations nettes", "ACTIF"),
    ("3010", "EPARGNE_VUE", "Dépôts à vue", "PASSIF"),
    ("3020", "EPARGNE_TERME", "Dépôts à terme", "PASSIF"),
    ("3510", "EMPRUNTS", "Emprunts et refinancements", "PASSIF"),
    ("5010", "CAPITAL", "Capital et dotations", "PASSIF"),
    ("5020", "RESERVES", "Réserves", "PASSIF"),
    ("5030", "RESULTAT", "Résultat de l'exercice", "PASSIF"),
    ("9990", "COMPTE_ATTENTE", "Compte d'attente (écarts non justifiés)", "PASSIF"),
]
PROV_BORNES = [0, 30, 90, 180, 360]
PROV_TAUX = np.array([0.01, 0.05, 0.25, 0.50, 0.75, 1.00])  # illustratifs


# --------------------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------------------
def d2i(s):
    """'2026-09-30' -> nombre de jours depuis 1970-01-01."""
    return int(np.datetime64(s, "D").astype("int64"))


def i2dt(arr):
    return pd.to_datetime(np.asarray(arr, dtype="int64"), unit="D")


def ids(prefix, n, width=7, start=1):
    return prefix + pd.Series(np.arange(start, start + n)).astype(str).str.zfill(width)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def month_ends(debut, arrete):
    m0, m1 = np.datetime64(debut, "M"), np.datetime64(arrete, "M")
    months = np.arange(m0, m1 + 1)
    ends = (months + 1).astype("datetime64[D]") - np.timedelta64(1, "D")
    a = np.datetime64(arrete, "D")
    ends = ends[ends <= a]
    if len(ends) == 0 or ends[-1] != a:
        ends = np.append(ends, a)
    return ends.astype("int64")


# --------------------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Générateur de données synthétiques d'IMF (CEMAC)")
    ap.add_argument("--out", default="data/raw", help="dossier de sortie")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--agences", type=int, default=12, help="nombre d'agences (max 15)")
    ap.add_argument("--clients", type=int, default=40000)
    ap.add_argument("--prets-par-client", type=float, default=1.5)
    ap.add_argument("--debut", default="2023-01-01")
    ap.add_argument("--arrete", default="2026-09-30", help="date d'arrêté des données")
    ap.add_argument("--par30-cible", type=float, default=0.07, help="PAR30 visé à la date d'arrêté (approx.)")
    ap.add_argument("--taux-anomalies", type=float, default=1.0, help="multiplicateur d'anomalies (0 = jeu propre)")
    ap.add_argument("--format", choices=["csv", "parquet"], default="csv")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.out, exist_ok=True)
    NA = max(1, min(args.agences, len(AGENCES)))
    N = args.clients
    debut_i, arrete_i = d2i(args.debut), d2i(args.arrete)
    assert arrete_i - debut_i > 200, "La période doit couvrir au moins ~7 mois."
    ANO = args.taux_anomalies

    def save(df, name):
        path = os.path.join(args.out, f"{name}.{'csv' if args.format == 'csv' else 'parquet'}")
        if args.format == "csv":
            df.to_csv(path, index=False, encoding="utf-8")
        else:
            df.to_parquet(path, index=False)
        print(f"  {name:<28} {len(df):>9,} lignes")

    print(f"Génération : {N:,} clients, {NA} agences, {args.debut} -> {args.arrete} (seed {args.seed})")

    # ----------------------------------------------------------------------------------
    # Agences, agents, produits
    # ----------------------------------------------------------------------------------
    ag_codes = np.array([f"AG{i + 1:02d}" for i in range(NA)])
    ag_w = rng.dirichlet(np.full(NA, 4.0))
    ag_risk = np.exp(rng.normal(0, 0.25, NA))
    ag_risk /= ag_risk.mean()
    agences_df = pd.DataFrame({
        "code_agence": ag_codes,
        "nom_agence": [AGENCES[i][0] for i in range(NA)],
        "region": [AGENCES[i][1] for i in range(NA)],
        "date_ouverture": i2dt(debut_i - rng.integers(200, 3000, NA)),
    })

    n_ag_agents = rng.integers(3, 7, NA)
    agent_ag = np.repeat(np.arange(NA), n_ag_agents)
    agent_offset = np.cumsum(n_ag_agents) - n_ag_agents
    agents_df = pd.DataFrame({
        "id_agent": ids("AGT", len(agent_ag), 4),
        "code_agence": ag_codes[agent_ag],
        "nom_agent": [f"{rng.choice(PRENOMS_M + PRENOMS_F)} {rng.choice(NOMS)}" for _ in agent_ag],
    })

    NP = len(PRODUITS)
    prod_df = pd.DataFrame(PRODUITS, columns=["id_produit", "libelle", "type_client", "taux_annuel",
                                              "durees", "montant_median", "montant_min", "montant_max",
                                              "risque"])
    produits_out = prod_df.drop(columns=["risque"]).copy()
    produits_out["durees"] = produits_out["durees"].apply(lambda d: "|".join(map(str, d)))

    # ----------------------------------------------------------------------------------
    # Clients
    # ----------------------------------------------------------------------------------
    is_group = rng.random(N) < 0.12
    c_ag = rng.choice(NA, N, p=ag_w)
    c_sect = rng.choice(len(SECTEURS), N, p=SECTEUR_POIDS)
    span_adh = (arrete_i - 40) - debut_i
    c_adh = debut_i + (span_adh * rng.random(N) ** 0.8).astype(np.int64)
    femme = rng.random(N) < 0.58
    prenoms = np.where(femme, rng.choice(PRENOMS_F, N), rng.choice(PRENOMS_M, N))
    noms = rng.choice(NOMS, N)
    age = rng.integers(22, 66, N)
    naiss = c_adh - age * 365 - rng.integers(0, 365, N)
    tel = rng.integers(600_000_000, 700_000_000, N).astype(str)

    grp_names = np.array([f"{rng.choice(GROUPES_PREFIXES)} {rng.choice(GROUPES_MOTS)} {rng.integers(1, 99)}"
                          for _ in range(is_group.sum())])
    clients = pd.DataFrame({
        "id_client": ids("C", N, 6),
        "type_client": np.where(is_group, "GROUPE", "INDIVIDUEL"),
        "nom": np.where(is_group, "", noms),
        "prenom": np.where(is_group, "", prenoms),
        "raison_sociale": "",
        "genre": np.where(is_group, "", np.where(femme, "F", "M")),
        "date_naissance": i2dt(naiss),
        "telephone": tel,
        "code_agence": ag_codes[c_ag],
        "secteur_activite": np.array(SECTEURS)[c_sect],
        "date_adhesion": i2dt(c_adh),
    })
    clients.loc[is_group, "raison_sociale"] = grp_names
    clients.loc[is_group, "date_naissance"] = pd.NaT
    clients.loc[is_group, "telephone"] = ""

    # ----------------------------------------------------------------------------------
    # Prêts
    # ----------------------------------------------------------------------------------
    L = int(N * args.prets_par_client)
    prod_idx = rng.choice(NP, L, p=PRODUIT_POIDS)
    prod_is_grp = np.array([p[2] == "GROUPE" for p in PRODUITS])[prod_idx]
    grp_ids, ind_ids = np.nonzero(is_group)[0], np.nonzero(~is_group)[0]
    if len(grp_ids) == 0:
        grp_ids = ind_ids
    l_cli = np.where(prod_is_grp, rng.choice(grp_ids, L), rng.choice(ind_ids, L))

    l_disb = c_adh[l_cli] + np.floor(rng.exponential(250, L)).astype(np.int64)
    over = l_disb > arrete_i - 10
    l_disb[over] = c_adh[l_cli][over] + np.floor(rng.random(over.sum()) * (arrete_i - 10 - c_adh[l_cli][over])).astype(np.int64)

    order = np.argsort(l_disb, kind="stable")
    prod_idx, l_cli, l_disb = prod_idx[order], l_cli[order], l_disb[order]

    med = np.array([p[5] for p in PRODUITS], float)[prod_idx]
    mn = np.array([p[6] for p in PRODUITS], float)[prod_idx]
    mx = np.array([p[7] for p in PRODUITS], float)[prod_idx]
    montant = np.clip(med * np.exp(0.5 * rng.standard_normal(L)), mn, mx)
    montant = np.maximum(np.round(montant / 5000) * 5000, np.round(mn / 5000) * 5000).astype(np.int64)

    duree = np.zeros(L, dtype=np.int64)
    taux = np.zeros(L)
    for pi, p in enumerate(PRODUITS):
        m = prod_idx == pi
        duree[m] = rng.choice(p[4], m.sum())
        taux[m] = p[3] + rng.choice([-0.02, 0.0, 0.0, 0.02], m.sum())

    l_ag = c_ag[l_cli]
    l_agent_idx = agent_offset[l_ag] + np.floor(rng.random(L) * n_ag_agents[l_ag]).astype(np.int64)
    sect_risk = np.array([SECTEUR_RISQUE[s] for s in SECTEURS])
    loan_risk = ag_risk[l_ag] * np.array([p[8] for p in PRODUITS])[prod_idx] * sect_risk[c_sect[l_cli]]
    loan_risk /= loan_risk.mean()
    is_agri = np.array([p[0] == "AGRI" for p in PRODUITS])[prod_idx]

    # ----------------------------------------------------------------------------------
    # Échéanciers (capital constant, intérêts sur capital restant dû)
    # ----------------------------------------------------------------------------------
    T = int(duree.sum())
    loan_idx = np.repeat(np.arange(L), duree)
    starts = np.cumsum(duree) - duree
    k = np.arange(T) - np.repeat(starts, duree) + 1
    disb_M = l_disb.astype("datetime64[D]").astype("datetime64[M]")
    dom = l_disb - disb_M.astype("datetime64[D]").astype("int64")
    dom = np.minimum(dom, 27)
    due_i = ((disb_M[loan_idx] + k).astype("datetime64[D]").astype("int64")) + dom[loan_idx]
    n_i = duree[loan_idx]
    base = np.round(montant / duree).astype(np.int64)
    cap_due = np.where(k < n_i, base[loan_idx], montant[loan_idx] - base[loan_idx] * (n_i - 1))
    bal_before = montant[loan_idx] - base[loan_idx] * (k - 1)
    int_due = np.round(bal_before * taux[loan_idx] / 12).astype(np.int64)
    tot_due = cap_due + int_due
    prod_i = prod_idx[loan_idx]
    agri_i = is_agri[loan_idx]
    due_month = i2dt(due_i).month.values

    # Tirages aléatoires fixés une fois (calibrage reproductible)
    u_prof = rng.random(L)
    u_stop = rng.beta(1.2, 1.8, L)
    r_delay_sel = rng.random(T)
    r_delay_mag = rng.random(T)
    r_part_sel = rng.random(T)
    r_part_frac = rng.random(T)
    r_comp_delay = rng.random(T)
    r_season = rng.random(T)
    r_canal = rng.random(T)

    def simulate(par_eff):
        p_def = np.clip(par_eff * loan_risk, 0, 0.6)
        p_late = np.clip(0.10 * loan_risk, 0, 0.35)
        p_part = np.clip(0.05 * loan_risk, 0, 0.20)
        c1, c2, c3 = p_def, p_def + p_late, p_def + p_late + p_part
        prof = np.zeros(L, dtype=np.int64)  # 0 bon, 1 retardataire, 2 partiel, 3 défaillant
        prof[(u_prof >= c1) & (u_prof < c2)] = 1
        prof[(u_prof >= c2) & (u_prof < c3)] = 2
        prof[u_prof < c1] = 3
        stop = 1 + np.minimum((u_stop * duree).astype(np.int64), duree - 1)
        pi_ = prof[loan_idx]

        delay = np.where(r_delay_sel < 0.75, 0, 1 + (r_delay_mag * 6).astype(np.int64))
        late = np.where(r_delay_sel < 0.50, (r_delay_mag * 4).astype(np.int64),
                        5 + (r_delay_mag * 40).astype(np.int64))
        delay = np.where(pi_ == 1, late, delay)
        season = agri_i & np.isin(due_month, (7, 8)) & (r_season < 0.40)
        delay = delay + np.where(season, 10 + (r_delay_mag * 30).astype(np.int64), 0)

        unpaid = (pi_ == 3) & (k >= stop[loan_idx])
        a_date = due_i + delay
        a_ok = (~unpaid) & (a_date <= arrete_i)
        partial = (pi_ == 2) & (r_part_sel < 0.35)
        frac = 0.5 + 0.45 * r_part_frac
        a_amt = np.where(partial, np.round(tot_due * frac), tot_due).astype(np.int64)
        a_cap = np.round(a_amt * cap_due / tot_due).astype(np.int64)
        a_cap = np.minimum(np.maximum(a_cap, a_amt - int_due), cap_due)
        b_date = a_date + 15 + (r_comp_delay * 45).astype(np.int64)
        b_ok = partial & (~unpaid) & a_ok & (b_date <= arrete_i)
        b_amt = np.where(partial, tot_due - a_amt, 0).astype(np.int64)
        b_cap = np.where(partial, cap_due - a_cap, 0).astype(np.int64)
        return dict(prof=prof, A_ok=a_ok, A_date=a_date, A_amt=a_amt, A_cap=a_cap,
                    B_ok=b_ok, B_date=b_date, B_amt=b_amt, B_cap=b_cap)

    BIG = np.int64(10 ** 9)

    def paid_by(sim, me):
        return (sim["A_amt"] * (sim["A_ok"] & (sim["A_date"] <= me))
                + sim["B_amt"] * (sim["B_ok"] & (sim["B_date"] <= me)))

    def dpd_at(sim, me):
        unsettled = (due_i <= me) & (paid_by(sim, me) < tot_due)
        mind = np.minimum.reduceat(np.where(unsettled, due_i, BIG), starts)
        return np.where(mind < BIG, me - mind, 0)

    def outst_at(sim, me):
        capb = (sim["A_cap"] * (sim["A_ok"] & (sim["A_date"] <= me))
                + sim["B_cap"] * (sim["B_ok"] & (sim["B_date"] <= me)))
        cap_paid = np.rint(np.bincount(loan_idx, weights=capb, minlength=L)).astype(np.int64)
        return np.where(l_disb <= me, montant - cap_paid, 0)

    def par30(sim, me):
        o, d = outst_at(sim, me), dpd_at(sim, me)
        tot = o.sum()
        return float(o[d > 30].sum() / tot) if tot > 0 else 0.0

    # Calibrage du taux de défaillance pour approcher le PAR30 cible
    par_eff = args.par30_cible
    sim = simulate(par_eff)
    for _ in range(6):
        obs = par30(sim, arrete_i)
        if abs(obs - args.par30_cible) < 0.002:
            break
        par_eff = min(0.6, par_eff * (args.par30_cible / obs if obs > 0 else 2.0))
        sim = simulate(par_eff)
    par_obs = par30(sim, arrete_i)

    # ----------------------------------------------------------------------------------
    # Tables prêts / échéanciers / remboursements
    # ----------------------------------------------------------------------------------
    d_arr = dpd_at(sim, arrete_i)
    paid_all = sim["A_amt"] * sim["A_ok"] + sim["B_amt"] * sim["B_ok"]
    n_unpaid = np.bincount(loan_idx, weights=(paid_all < tot_due).astype(float), minlength=L)
    solde = n_unpaid == 0
    last_pay = np.maximum.reduceat(np.maximum(np.where(sim["A_ok"], sim["A_date"], 0),
                                              np.where(sim["B_ok"], sim["B_date"], 0)), starts)
    statut = np.where(solde, "SOLDE", np.where(d_arr > 90, "CONTENTIEUX", "EN_COURS"))
    last_due = np.maximum.reduceat(due_i, starts)

    prets = pd.DataFrame({
        "id_pret": ids("P", L),
        "id_client": clients["id_client"].values[l_cli],
        "id_produit": np.array([p[0] for p in PRODUITS])[prod_idx],
        "id_agent": agents_df["id_agent"].values[l_agent_idx],
        "date_decaissement": i2dt(l_disb),
        "montant_decaisse": montant,
        "taux_annuel": np.round(taux, 4),
        "duree_mois": duree,
        "periodicite": "MENSUELLE",
        "frais_dossier": (montant * 0.015).round().astype(np.int64),
        "date_fin_prevue": i2dt(last_due),
        "statut": statut,
        "date_solde": pd.to_datetime(np.where(solde, last_pay, 0), unit="D").where(solde),
    })
    prets["_ag"] = ag_codes[l_ag]

    echeanciers = pd.DataFrame({
        "id_echeance": ids("E", T, 8),
        "id_pret": prets["id_pret"].values[loan_idx],
        "num_echeance": k,
        "date_echeance": i2dt(due_i),
        "capital_du": cap_due,
        "interets_dus": int_due,
        "total_du": tot_due,
    })

    canal = np.where(r_canal < 0.60, "ESPECES", np.where(r_canal < 0.90, "MOBILE_MONEY", "VIREMENT"))
    pid = prets["id_pret"].values[loan_idx]
    rows = []
    for tag in ("A", "B"):
        m = sim[f"{tag}_ok"]
        amt, cap, dt = sim[f"{tag}_amt"][m], sim[f"{tag}_cap"][m], sim[f"{tag}_date"][m]
        rows.append(pd.DataFrame({
            "id_pret": pid[m], "num_echeance": k[m], "date_paiement": dt,
            "montant_capital": cap, "montant_interets": amt - cap, "montant_total": amt, "canal": canal[m],
        }))
    remb = pd.concat(rows, ignore_index=True).sort_values(["date_paiement", "id_pret", "num_echeance"],
                                                          kind="stable").reset_index(drop=True)
    remb.insert(0, "id_remboursement", ids("R", len(remb), 8))
    remb["date_paiement"] = i2dt(remb["date_paiement"].values)

    # ----------------------------------------------------------------------------------
    # Épargne
    # ----------------------------------------------------------------------------------
    has = rng.random(N) < 0.65
    cl_idx = np.nonzero(has)[0]
    ne = len(cl_idx)
    open_i = np.minimum(c_adh[cl_idx] + rng.integers(0, 60, ne), arrete_i - 20)
    typ = np.where(rng.random(ne) < 0.85, 0, 1)  # 0 = VUE, 1 = TERME
    term_m = np.where(typ == 1, rng.choice([6, 12, 24], ne), 0)
    comptes = pd.DataFrame({
        "id_compte": ids("S", ne),
        "id_client": clients["id_client"].values[cl_idx],
        "code_agence": ag_codes[c_ag[cl_idx]],
        "type_compte": np.where(typ == 0, "VUE", "TERME"),
        "date_ouverture": i2dt(open_i),
        "duree_terme_mois": pd.array(np.where(typ == 1, term_m, 0), dtype="Int64"),
        "taux_remuneration": np.where(typ == 0, 0.015, np.where(term_m == 6, 0.035, np.where(term_m == 12, 0.045, 0.055))),
    })
    comptes.loc[comptes["type_compte"] == "VUE", "duree_terme_mois"] = pd.NA

    mv_acc, mv_date, mv_sign, mv_amt = [], [], [], []
    # comptes à vue : marche aléatoire sans solde négatif
    iv = np.nonzero(typ == 0)[0]
    nv, K = len(iv), 24
    span = (arrete_i - open_i[iv]).astype(float)
    n_mov = np.clip(2 + (span / 30 * 0.45).astype(int) + rng.integers(0, 3, nv), 2, K)
    u = rng.random((nv, K))
    u[np.arange(K)[None, :] >= n_mov[:, None]] = 2.0
    u.sort(axis=1)
    dates = open_i[iv][:, None] + (np.minimum(u, 0.999999) * span[:, None]).astype(np.int64)
    valid = u < 1.0
    zz = rng.standard_normal((nv, K))
    rr = rng.random((nv, K))
    fr = 0.1 + 0.6 * rng.random((nv, K))
    bal = np.zeros(nv)
    for j in range(K):
        dep = np.maximum(np.round(np.exp(np.log(40_000) + 0.9 * zz[:, j]) / 500) * 500, 5_000)
        want_dep = (j == 0) | (bal < 5_000) | (rr[:, j] < 0.62)
        wd = np.floor(bal * fr[:, j] / 500) * 500
        amt = np.where(want_dep, dep, wd)
        ok = valid[:, j] & (amt > 0)
        sgn = np.where(want_dep, 1, -1)
        bal += np.where(ok, sgn * amt, 0)
        mv_acc.append(iv[ok]); mv_date.append(dates[ok, j]); mv_sign.append(sgn[ok]); mv_amt.append(amt[ok])
    # comptes à terme : un dépôt, retrait à l'échéance dans 70 % des cas
    it = np.nonzero(typ == 1)[0]
    if len(it):
        dep_t = np.maximum(np.round(np.exp(np.log(500_000) + 0.8 * rng.standard_normal(len(it))) / 10_000) * 10_000, 100_000)
        mv_acc.append(it); mv_date.append(open_i[it]); mv_sign.append(np.ones(len(it), int)); mv_amt.append(dep_t)
        mat = open_i[it] + term_m[it] * 30
        wd_t = (mat <= arrete_i) & (rng.random(len(it)) < 0.70)
        mv_acc.append(it[wd_t]); mv_date.append(mat[wd_t]); mv_sign.append(-np.ones(wd_t.sum(), int)); mv_amt.append(dep_t[wd_t])
    mv_acc, mv_date = np.concatenate(mv_acc), np.concatenate(mv_date).astype(np.int64)
    mv_sign, mv_amt = np.concatenate(mv_sign), np.concatenate(mv_amt).astype(np.int64)
    o = np.argsort(mv_date, kind="stable")
    mv_acc, mv_date, mv_sign, mv_amt = mv_acc[o], mv_date[o], mv_sign[o], mv_amt[o]
    mouvements = pd.DataFrame({
        "id_mouvement": ids("M", len(mv_acc), 8),
        "id_compte": comptes["id_compte"].values[mv_acc],
        "date_mouvement": i2dt(mv_date),
        "type_mouvement": np.where(mv_sign > 0, "DEPOT", "RETRAIT"),
        "montant": mv_amt,
    })
    mv_ag, mv_typ = c_ag[cl_idx][mv_acc], typ[mv_acc]

    # ----------------------------------------------------------------------------------
    # Balance comptable mensuelle (cohérente avec le portefeuille)
    # ----------------------------------------------------------------------------------
    pay_dates = np.concatenate([sim["A_date"][sim["A_ok"]], sim["B_date"][sim["B_ok"]]])
    pay_int = np.concatenate([(sim["A_amt"] - sim["A_cap"])[sim["A_ok"]], (sim["B_amt"] - sim["B_cap"])[sim["B_ok"]]])
    o = np.argsort(pay_dates, kind="stable")
    pay_dates, cs_int = pay_dates[o], np.concatenate([[0], np.cumsum(pay_int[o])])

    def cum_int(d):
        return cs_int[np.searchsorted(pay_dates, d, side="right")]

    ME = month_ends(args.debut, args.arrete)
    capital = float(np.round(0.15 * outst_at(sim, arrete_i).sum(), -6))
    immos = 12_000_000.0 * NA
    caisse = 3_000_000.0 * NA
    bal_rows = []
    for me in ME:
        o_, d_ = outst_at(sim, me), dpd_at(sim, me)
        bucket = np.searchsorted(PROV_BORNES, d_, side="left")
        prov = o_ * PROV_TAUX[bucket]
        agg = lambda w: np.bincount(l_ag, weights=w, minlength=NA)
        sains, douteux, litig = agg(o_ * (d_ <= 30)), agg(o_ * ((d_ > 30) & (d_ <= 90))), agg(o_ * (d_ > 90))
        provs = agg(prov)
        mk = mv_date <= me
        e_vue = np.bincount(mv_ag[mk & (mv_typ == 0)], weights=(mv_sign * mv_amt)[mk & (mv_typ == 0)], minlength=NA)
        e_term = np.bincount(mv_ag[mk & (mv_typ == 1)], weights=(mv_sign * mv_amt)[mk & (mv_typ == 1)], minlength=NA)
        year_end_prev = d2i(f"{int(str(np.datetime64(int(me), 'D'))[:4]) - 1}-12-31")
        reserves = 0.25 * cum_int(year_end_prev)
        resultat = 0.25 * (cum_int(me) - cum_int(year_end_prev))
        other_assets = caisse + sains.sum() + douteux.sum() + litig.sum() - provs.sum() + immos
        base_passif = e_vue.sum() + e_term.sum() + capital + reserves + resultat
        emprunts = max(0.0, other_assets * 1.07 - base_passif)
        banque = base_passif + emprunts - other_assets
        dte = np.datetime64(int(me), "D")
        for i in range(NA):
            for code, val in (("CRD_SAINS", sains[i]), ("CRD_DOUTEUX", douteux[i]), ("CRD_LITIGIEUX", litig[i]),
                              ("PROVISIONS", -provs[i]), ("EPARGNE_VUE", e_vue[i]), ("EPARGNE_TERME", e_term[i])):
                bal_rows.append((dte, ag_codes[i], code, round(float(val))))
        for code, val in (("CAISSE", caisse), ("BANQUE", banque), ("IMMOBILISATIONS", immos), ("EMPRUNTS", emprunts),
                          ("CAPITAL", capital), ("RESERVES", reserves), ("RESULTAT", resultat)):
            bal_rows.append((dte, "SIEGE", code, round(float(val))))
    pc = pd.DataFrame(PLAN_COMPTABLE, columns=["compte", "code_poste", "libelle", "classe"])
    balance = pd.DataFrame(bal_rows, columns=["date_arrete", "code_agence", "code_poste", "solde"])
    balance = balance.merge(pc, on="code_poste", how="left")[["date_arrete", "code_agence", "compte", "code_poste", "libelle", "classe", "solde"]]
    balance["date_arrete"] = pd.to_datetime(balance["date_arrete"])

    # Contrôle d'équilibre
    chk = balance.groupby(["date_arrete", "classe"])["solde"].sum().unstack()
    assert (chk["ACTIF"] - chk["PASSIF"]).abs().max() < 5 * NA, "Balance déséquilibrée"

    # ----------------------------------------------------------------------------------
    # Injection d'anomalies (tracées)
    # ----------------------------------------------------------------------------------
    log = []

    def note(table, cle, typ_, desc):
        log.append(pd.DataFrame({"table": table, "cle": np.asarray(cle).astype(str), "type_anomalie": typ_, "description": desc}))

    def pick(n_base, pool_size):
        n = int(round(n_base * ANO))
        return rng.choice(pool_size, min(n, pool_size), replace=False) if n > 0 else np.array([], dtype=int)

    if ANO > 0:
        # clients : doublons
        pool = np.nonzero(~is_group)[0]
        src = rng.choice(pool, min(max(5, int(0.006 * N * ANO)), len(pool)), replace=False)
        dup = clients.iloc[src].copy()
        dup["id_client"] = ids("C", len(dup), 6, start=N + 1).values
        mode = rng.integers(0, 3, len(dup))
        dup["nom"] = [n.upper() if m == 0 else strip_accents(n) if m == 1 else n + " " for n, m in zip(dup["nom"], mode)]
        dup["prenom"] = [strip_accents(p) if m == 2 else p for p, m in zip(dup["prenom"], mode)]
        clients = pd.concat([clients, dup], ignore_index=True)
        note("clients", dup["id_client"], "doublon_client", [f"doublon probable de {c}" for c in clients["id_client"].values[src]])
        # clients : code agence mal formé / inconnu
        i1 = pick(0.004 * N, N)
        v = np.array(["{}", "{}", "{}"])
        bad = [(c.lower() if m == 0 else c[:2] + "-" + c[2:] if m == 1 else " " + c) for c, m in
               zip(clients["code_agence"].values[i1], rng.integers(0, 3, len(i1)))]
        clients.loc[clients.index[i1], "code_agence"] = bad
        note("clients", clients["id_client"].values[i1], "code_agence_mal_forme", "format de code agence non conforme")
        i2 = pick(0.0005 * N, N)
        clients.loc[clients.index[i2], "code_agence"] = "AG99"
        note("clients", clients["id_client"].values[i2], "code_agence_inconnu", "code agence absent du référentiel")
        # clients : secteur manquant, téléphone invalide, mineur
        i3 = pick(0.015 * N, N)
        clients.loc[clients.index[i3], "secteur_activite"] = None
        note("clients", clients["id_client"].values[i3], "secteur_manquant", "secteur d'activité non renseigné")
        i4 = pick(0.008 * N, N)
        i4 = i4[~is_group[i4]]
        clients.loc[clients.index[i4], "telephone"] = [str(t)[:7] for t in clients["telephone"].values[i4]]
        note("clients", clients["id_client"].values[i4], "telephone_invalide", "numéro de téléphone à 7 chiffres")
        i5 = pick(0.002 * N, N)
        i5 = i5[~is_group[i5]]
        clients.loc[clients.index[i5], "date_naissance"] = clients["date_adhesion"].values[i5] - pd.to_timedelta(rng.integers(3000, 6000, len(i5)), unit="D")
        note("clients", clients["id_client"].values[i5], "client_mineur", "date de naissance incohérente (âge < 18 ans)")

        # prêts : décaissement avant adhésion
        j1 = pick(0.003 * L, L)
        adh_pret = pd.Series(c_adh[l_cli][j1])
        prets.loc[prets.index[j1], "date_decaissement"] = i2dt(adh_pret.values - rng.integers(5, 200, len(j1)))
        note("prets", prets["id_pret"].values[j1], "decaissement_avant_adhesion", "date de décaissement antérieure à l'adhésion du client")
        # prêts : statut SOLDE alors que du capital reste dû
        open_loans = np.nonzero(~solde)[0]
        j2 = rng.choice(open_loans, min(max(3, int(12 * ANO)), len(open_loans)), replace=False)
        prets.loc[prets.index[j2], "statut"] = "SOLDE"
        note("prets", prets["id_pret"].values[j2], "statut_incoherent", "statut SOLDE alors qu'il reste du capital dû")

        # échéanciers : prêts sans échéancier, doublons de lignes
        j3 = pick(0.002 * L, L)
        no_sched = prets["id_pret"].values[j3]
        echeanciers = echeanciers[~echeanciers["id_pret"].isin(no_sched)]
        note("echeanciers", no_sched, "pret_sans_echeancier", "aucune échéance pour ce prêt")
        j4 = rng.choice(len(echeanciers), min(int(0.0005 * T * ANO) + 1, len(echeanciers)), replace=False)
        dups = echeanciers.iloc[j4].copy()
        echeanciers = pd.concat([echeanciers, dups], ignore_index=True)
        note("echeanciers", dups["id_echeance"], "echeance_dupliquee", "ligne d'échéance présente en double")

        # remboursements : négatifs, doublons, dates futures, orphelins
        nR = len(remb)
        r1 = pick(0.0005 * nR, nR)
        for c in ("montant_capital", "montant_interets", "montant_total"):
            remb.loc[remb.index[r1], c] = -remb.loc[remb.index[r1], c]
        note("remboursements", remb["id_remboursement"].values[r1], "montant_negatif", "paiement avec montants négatifs")
        r2 = pick(0.001 * nR, nR)
        dd = remb.iloc[r2].copy()
        dd["id_remboursement"] = ids("R", len(dd), 8, start=nR + 1).values
        remb = pd.concat([remb, dd], ignore_index=True)
        note("remboursements", dd["id_remboursement"], "paiement_double", [f"doublon du paiement {x}" for x in remb["id_remboursement"].values[r2]])
        r3 = pick(0.0002 * nR, nR)
        remb.loc[remb.index[r3], "date_paiement"] = i2dt(arrete_i + rng.integers(5, 60, len(r3)))
        note("remboursements", remb["id_remboursement"].values[r3], "date_future", "date de paiement postérieure à la date d'arrêté")
        r4 = pick(0.0003 * nR, nR)
        remb.loc[remb.index[r4], "id_pret"] = "P9999999"
        note("remboursements", remb["id_remboursement"].values[r4], "pret_inexistant", "paiement rattaché à un prêt inexistant")

        # balance : écarts de rapprochement portefeuille / comptabilité
        last, prev = balance["date_arrete"].max(), np.sort(balance["date_arrete"].unique())[-2]
        for dte, i, pct in ((last, 0, 0.012), (last, min(2, NA - 1), -0.007), (prev, 0, 0.012)):
            m = (balance["date_arrete"] == dte) & (balance["code_agence"] == ag_codes[i]) & (balance["code_poste"] == "CRD_SAINS")
            delta = int(round(balance.loc[m, "solde"].iloc[0] * pct, -3))
            balance.loc[m, "solde"] += delta
            att = pd.DataFrame([(dte, "SIEGE", "9990", "COMPTE_ATTENTE", "Compte d'attente (écarts non justifiés)", "PASSIF", delta)], columns=balance.columns)
            balance = pd.concat([balance, att], ignore_index=True)
            note("balance_comptable", [f"{pd.Timestamp(dte).date()}|{ag_codes[i]}|CRD_SAINS"], "ecart_rapprochement", f"écart de {delta:,} FCFA entre sous-ledger prêts et grand livre".replace(",", " "))

    # ----------------------------------------------------------------------------------
    # Sauvegarde
    # ----------------------------------------------------------------------------------
    prets = prets.drop(columns=["_ag"])
    balance = balance.sort_values(["date_arrete", "code_agence", "compte"]).reset_index(drop=True)
    anomalies = (pd.concat(log, ignore_index=True) if log else
                 pd.DataFrame(columns=["table", "cle", "type_anomalie", "description"]))
    print("\nFichiers écrits dans", os.path.abspath(args.out))
    save(agences_df, "agences")
    save(agents_df, "agents")
    save(produits_out, "produits")
    save(pc, "plan_comptable")
    save(clients, "clients")
    save(prets, "prets")
    save(echeanciers, "echeanciers")
    save(remb, "remboursements")
    save(comptes, "epargne_comptes")
    save(mouvements, "epargne_mouvements")
    save(balance, "balance_comptable")
    save(anomalies, "anomalies_injectees")

    manifest = {
        "parametres": vars(args),
        "date_arrete": args.arrete,
        "portefeuille_encours_fcfa": int(outst_at(sim, arrete_i).sum()),
        "par30_observe": round(par_obs, 4),
        "par90_observe": round(float(outst_at(sim, arrete_i)[d_arr > 90].sum() / max(1, outst_at(sim, arrete_i).sum())), 4),
        "nb_clients": int(len(clients)), "nb_prets": int(len(prets)),
        "nb_anomalies_injectees": int(len(anomalies)),
        "avertissement": "Données entièrement fictives. Plan comptable et taux de provisionnement illustratifs.",
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nEncours à l'arrêté : {manifest['portefeuille_encours_fcfa']:,} FCFA".replace(",", " "))
    print(f"PAR30 observé : {par_obs:.1%} (cible {args.par30_cible:.1%}) | PAR90 : {manifest['par90_observe']:.1%}")
    print(f"Anomalies injectées : {len(anomalies)}")


if __name__ == "__main__":
    main()
