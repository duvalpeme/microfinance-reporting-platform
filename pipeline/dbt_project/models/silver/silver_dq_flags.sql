{#- Pour chaque clé (client, prêt, échéance, paiement...), la liste des règles qualité déclenchées.
    Les identifiants ont des préfixes distincts (C, P, E, R...) : la clé est unique toutes tables confondues. -#}
select
    cle,
    string_agg(regle_id, ',' order by regle_id) as dq_regles
from {{ source('quality', 'violations') }}
group by cle
