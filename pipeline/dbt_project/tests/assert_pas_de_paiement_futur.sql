-- Aucun paiement silver postérieur à la date d'arrêté.
select id_remboursement
from {{ ref('silver_remboursements') }}
where date_paiement > (select cast(valeur as date) from {{ source('bronze', '_meta') }} where cle = 'date_arrete')
