-- Conservation : échéances silver = identifiants distincts du bronze.
select
    (select count(distinct id_echeance) from {{ source('bronze', 'echeanciers') }}) as nb_distincts_bronze,
    (select count(*) from {{ ref('silver_echeanciers') }}) as nb_silver
where nb_distincts_bronze <> nb_silver
