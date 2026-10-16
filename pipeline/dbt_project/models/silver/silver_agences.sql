select
    code_agence,
    nom_agence,
    region,
    try_cast(date_ouverture as date) as date_ouverture
from {{ source('bronze', 'agences') }}

union all

{# Membre technique : reçoit les clients dont le code agence est introuvable, pour que leur encours reste visible. #}
select 'INCONNU', 'Agence non identifiée', 'INCONNU', null
