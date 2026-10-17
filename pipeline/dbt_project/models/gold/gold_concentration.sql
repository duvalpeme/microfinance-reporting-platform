{#- Répartition de l'encours par agence, produit, secteur et type de client, avec le PAR 30 de chaque segment. -#}
with base as (
    select * from {{ ref('gold_encours_pret') }} where encours > 0
),

segments as (
    select 'AGENCE' as dimension, code_agence as segment, * from base
    union all
    select 'PRODUIT', id_produit, * from base
    union all
    select 'SECTEUR', secteur_activite, * from base
    union all
    select 'TYPE_CLIENT', type_client, * from base
)

select
    dimension,
    segment,
    count(*) as nb_prets,
    sum(encours) as encours,
    round(sum(encours) / sum(sum(encours)) over (partition by dimension), 4) as part_encours,
    round(sum(encours) filter (where evaluable and jours_retard > 30)
          / nullif(sum(encours) filter (where evaluable), 0), 4) as par30
from segments
group by dimension, segment
order by dimension, encours desc
