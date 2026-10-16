select
    id_compte,
    id_client,
    code_agence,
    type_compte,
    try_cast(date_ouverture as date) as date_ouverture,
    try_cast(duree_terme_mois as integer) as duree_terme_mois,
    try_cast(taux_remuneration as double) as taux_remuneration
from {{ source('bronze', 'epargne_comptes') }}
