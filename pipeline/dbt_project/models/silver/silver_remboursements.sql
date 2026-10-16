{#- Paiements valides uniquement. Les lignes en infraction (action = quarantaine) sont retirées ici
    et conservées intégralement dans quarantine.quarantine_remboursements. Rien n'est supprimé en silence. -#}
select
    id_remboursement,
    id_pret,
    try_cast(num_echeance as integer) as num_echeance,
    try_cast(date_paiement as date) as date_paiement,
    try_cast(montant_capital as bigint) as montant_capital,
    try_cast(montant_interets as bigint) as montant_interets,
    try_cast(montant_total as bigint) as montant_total,
    canal
from {{ source('bronze', 'remboursements') }}
where id_remboursement not in (
    select cle
    from {{ source('quality', 'violations') }}
    where table_source = 'remboursements' and action = 'quarantaine'
)
