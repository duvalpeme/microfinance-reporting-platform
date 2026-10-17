{#- Qualité du portefeuille par agence et au total (ligne TOTAL), à la date d'arrêté.
    PAR x = encours des prêts ayant au moins un impayé de plus de x jours / encours évaluable. -#}
with base as (
    select * from {{ ref('gold_encours_pret') }} where encours > 0
),

par_agence as (
    select
        code_agence,
        count(*) as nb_prets_actifs,
        sum(encours) as encours_total,
        coalesce(sum(encours) filter (where evaluable), 0) as encours_evaluable,
        coalesce(sum(encours) filter (where not evaluable), 0) as encours_non_evaluable,
        coalesce(sum(encours) filter (where evaluable and jours_retard >= 1), 0) as encours_par1,
        coalesce(sum(encours) filter (where evaluable and jours_retard > 30), 0) as encours_par30,
        coalesce(sum(encours) filter (where evaluable and jours_retard > 90), 0) as encours_par90,
        coalesce(sum(encours) filter (where evaluable and jours_retard > 30 and retard_incertain), 0) as encours_par30_incertain,
        sum(provision) as provisions
    from base
    group by 1
),

avec_total as (
    select * from par_agence
    union all
    select
        'TOTAL', sum(nb_prets_actifs), sum(encours_total), sum(encours_evaluable), sum(encours_non_evaluable),
        sum(encours_par1), sum(encours_par30), sum(encours_par90), sum(encours_par30_incertain), sum(provisions)
    from par_agence
)

select
    code_agence,
    nb_prets_actifs,
    encours_total,
    encours_evaluable,
    encours_non_evaluable,
    encours_par1,
    encours_par30,
    encours_par90,
    round(encours_par1 / nullif(encours_evaluable, 0), 4) as par1,
    round(encours_par30 / nullif(encours_evaluable, 0), 4) as par30,
    round(encours_par90 / nullif(encours_evaluable, 0), 4) as par90,
    provisions,
    round(provisions / nullif(encours_total, 0), 4) as taux_provisionnement,
    round(provisions / nullif(encours_par30, 0), 4) as couverture_par30,
    encours_par30_incertain,
    round((encours_par30 - encours_par30_incertain) / nullif(encours_evaluable, 0), 4) as par30_hors_incertain
from avec_total
