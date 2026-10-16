select
    try_cast(date_arrete as date) as date_arrete,
    code_agence,
    compte,
    code_poste,
    libelle,
    classe,
    try_cast(solde as bigint) as solde
from {{ source('bronze', 'balance_comptable') }}
