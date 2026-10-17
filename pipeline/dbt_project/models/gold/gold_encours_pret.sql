{#- Une ligne par prêt à la date d'arrêté : encours (capital restant dû), jours de retard, tranche, provision.
    Jours de retard = ancienneté de la plus ancienne échéance échue et non entièrement payée.
    Deux réserves portées par des colonnes, pour ne pas fausser le PAR en silence :
      - evaluable = false  : prêt sans échéancier (règle ECH_01), le retard est incalculable
      - retard_incertain   : un paiement de ce prêt est en quarantaine (REM_01 / REM_03) ; l'échéance
                             correspondante apparaît impayée alors qu'elle l'est peut-être à tort -#}
with arrete as (
    select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete'
),

paye as (
    select r.id_pret, r.num_echeance, sum(r.montant_total) as paye_total
    from {{ ref('silver_remboursements') }} r
    cross join arrete a
    where r.date_paiement <= a.d
    group by 1, 2
),

echues as (
    select e.id_pret, e.date_echeance, e.total_du, coalesce(p.paye_total, 0) as paye_total
    from {{ ref('silver_echeanciers') }} e
    cross join arrete a
    left join paye p on p.id_pret = e.id_pret and p.num_echeance = e.num_echeance
    where e.date_echeance <= a.d
),

plus_ancienne as (
    select id_pret, min(date_echeance) filter (where paye_total < total_du) as date_impayee
    from echues
    group by 1
),

capital as (
    select r.id_pret, sum(r.montant_capital) as capital_rembourse
    from {{ ref('silver_remboursements') }} r
    cross join arrete a
    where r.date_paiement <= a.d
    group by 1
),

incertain as (
    select distinct id_pret
    from {{ ref('quarantine_remboursements') }}
    where regles like '%REM_01%' or regles like '%REM_03%'
),

base as (
    select
        p.id_pret,
        p.id_client,
        p.id_produit,
        p.id_agent,
        c.code_agence,
        c.secteur_activite,
        c.type_client,
        p.date_decaissement,
        p.montant_decaisse,
        coalesce(k.capital_rembourse, 0) as capital_rembourse,
        p.montant_decaisse - coalesce(k.capital_rembourse, 0) as encours,
        coalesce(date_diff('day', pa.date_impayee, a.d), 0) as jours_retard,
        coalesce(p.dq_regles, '') not like '%ECH_01%' as evaluable,
        i.id_pret is not null as retard_incertain,
        p.dq_regles
    from {{ ref('silver_prets') }} p
    join {{ ref('silver_clients') }} c on c.id_client = p.id_client
    cross join arrete a
    left join capital k on k.id_pret = p.id_pret
    left join plus_ancienne pa on pa.id_pret = p.id_pret
    left join incertain i on i.id_pret = p.id_pret
    where p.date_decaissement <= a.d
)

select
    b.*,
    t.tranche_retard,
    t.taux_provision,
    round(b.encours * t.taux_provision) as provision,
    case
        when b.encours <= 0 then 'SOLDE'
        when b.jours_retard > 90 then 'CONTENTIEUX'
        else 'EN_COURS'
    end as statut_gold
from base b
join {{ ref('gold_taux_provision') }} t
    on b.jours_retard between t.jours_min and t.jours_max
