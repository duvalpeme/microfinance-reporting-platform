-- Conservation : clients bronze = clients silver + doublons retirés (règle CLI_01).
select
    (select count(*) from {{ source('bronze', 'clients') }}) as nb_bronze,
    (select count(*) from {{ ref('silver_clients') }}) as nb_silver,
    (select count(*) from {{ source('quality', 'violations') }} where regle_id = 'CLI_01_DOUBLON') as nb_doublons
where nb_bronze <> nb_silver + nb_doublons
