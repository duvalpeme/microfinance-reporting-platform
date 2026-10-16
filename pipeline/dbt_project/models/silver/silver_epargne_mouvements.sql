select
    id_mouvement,
    id_compte,
    try_cast(date_mouvement as date) as date_mouvement,
    type_mouvement,
    try_cast(montant as bigint) as montant
from {{ source('bronze', 'epargne_mouvements') }}
