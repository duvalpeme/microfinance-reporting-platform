-- Conservation : lignes bronze = lignes silver + lignes en quarantaine. Rien ne disparaît en silence.
select
    (select count(*) from {{ source('bronze', 'remboursements') }}) as nb_bronze,
    (select count(*) from {{ ref('silver_remboursements') }}) as nb_silver,
    (select count(*) from {{ ref('quarantine_remboursements') }}) as nb_quarantaine
where nb_bronze <> nb_silver + nb_quarantaine
