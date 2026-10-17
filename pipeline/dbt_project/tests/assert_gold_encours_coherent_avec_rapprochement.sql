-- Deux calculs indépendants de l'encours (par prêt, et par agence au rapprochement) doivent donner le même total.
with arrete as (select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete')
select
    (select sum(encours) from {{ ref('gold_encours_pret') }}) as encours_pret,
    (select sum(r.encours_sous_ledger) from {{ ref('gold_rapprochement') }} r cross join arrete a where r.date_arrete = a.d) as encours_rapprochement
where encours_pret <> encours_rapprochement
