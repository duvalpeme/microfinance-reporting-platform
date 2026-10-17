{#- Barème de provisionnement par tranche de retard.
    ILLUSTRATIF : à remplacer par le barème réglementaire applicable à la catégorie de l'institution. -#}
select * from (
    values
        (1, 'A_JOUR',     0,     0,     0.01),
        (2, '1-30',       1,    30,     0.05),
        (3, '31-90',     31,    90,     0.25),
        (4, '91-180',    91,   180,     0.50),
        (5, '181-360',  181,   360,     0.75),
        (6, '>360',     361, 99999,     1.00)
) as t(ordre, tranche_retard, jours_min, jours_max, taux_provision)
