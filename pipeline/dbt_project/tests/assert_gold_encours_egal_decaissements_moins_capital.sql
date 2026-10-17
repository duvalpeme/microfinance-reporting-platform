-- Invariant : encours gold = décaissements - capital remboursé, calculés indépendamment depuis le silver.
with arrete as (select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete')
select
    (select sum(encours) from {{ ref('gold_encours_pret') }}) as encours_gold,
    (select sum(p.montant_decaisse) from {{ ref('silver_prets') }} p cross join arrete a where p.date_decaissement <= a.d)
  - (select sum(r.montant_capital) from {{ ref('silver_remboursements') }} r cross join arrete a where r.date_paiement <= a.d) as encours_recalcule
where encours_gold <> encours_recalcule
