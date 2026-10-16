{#- Échéances dédoublonnées (ECH_02) : une seule ligne par identifiant. -#}
with ranked as (
    select
        *,
        row_number() over (partition by id_echeance order by id_echeance) as rn
    from {{ source('bronze', 'echeanciers') }}
)

select
    id_echeance,
    id_pret,
    try_cast(num_echeance as integer) as num_echeance,
    try_cast(date_echeance as date) as date_echeance,
    try_cast(capital_du as bigint) as capital_du,
    try_cast(interets_dus as bigint) as interets_dus,
    try_cast(total_du as bigint) as total_du
from ranked
where rn = 1
