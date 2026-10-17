{#- Les 20 plus gros engagements par client, rapportés à l'encours total et aux fonds propres comptables.
    Les limites réglementaires de division des risques dépendent du texte applicable : elles ne sont pas codées ici. -#}
with arrete as (
    select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete'
),

fonds_propres as (
    select sum(b.solde) as montant
    from {{ ref('silver_balance_comptable') }} b
    cross join arrete a
    where b.date_arrete = a.d and b.code_poste in ('CAPITAL', 'RESERVES', 'RESULTAT')
),

total as (
    select sum(encours) as encours_total from {{ ref('gold_encours_pret') }} where encours > 0
),

par_client as (
    select
        e.id_client,
        count(*) as nb_prets,
        sum(e.encours) as encours,
        max(e.jours_retard) as jours_retard_max
    from {{ ref('gold_encours_pret') }} e
    where e.encours > 0
    group by 1
)

select
    row_number() over (order by p.encours desc) as rang,
    p.id_client,
    coalesce(nullif(c.raison_sociale, ''), c.prenom || ' ' || c.nom) as client,
    c.type_client,
    c.code_agence,
    p.nb_prets,
    p.encours,
    p.jours_retard_max,
    round(p.encours / t.encours_total, 5) as part_encours_total,
    f.montant as fonds_propres,
    round(p.encours / nullif(f.montant, 0), 5) as part_fonds_propres
from par_client p
join {{ ref('silver_clients') }} c on c.id_client = p.id_client
cross join total t
cross join fonds_propres f
order by p.encours desc
limit 20
