select
    id_produit,
    libelle,
    type_client,
    try_cast(taux_annuel as double) as taux_annuel,
    durees,
    try_cast(montant_median as bigint) as montant_median,
    try_cast(montant_min as bigint) as montant_min,
    try_cast(montant_max as bigint) as montant_max
from {{ source('bronze', 'produits') }}
