{#- Décision unique de publication des états : bloquée si un contrôle qualité critique est en infraction
    OU si une agence présente un écart de rapprochement à justifier à la date d'arrêté.
    C'est cette table que le tableau de bord lira pour afficher le statut des états. -#}
with arrete as (
    select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete'
),

qualite as (
    select decision, regles_bloquantes from {{ source('quality', 'gate') }}
),

ecarts as (
    select count(*) as nb_agences, string_agg(r.code_agence, ', ' order by r.code_agence) as agences
    from {{ ref('gold_rapprochement') }} r
    cross join arrete a
    where r.date_arrete = a.d and r.statut = 'ECART_A_JUSTIFIER'
)

select
    a.d as date_arrete,
    case when q.decision = 'BLOQUEE' or e.nb_agences > 0 then 'BLOQUEE' else 'OUVERTE' end as decision,
    nullif(concat_ws(' | ',
        case when q.decision = 'BLOQUEE' then 'Contrôles qualité critiques : ' || q.regles_bloquantes end,
        case when e.nb_agences > 0 then 'Écart de rapprochement à justifier : ' || e.agences end
    ), '') as motifs
from arrete a
cross join qualite q
cross join ecarts e
