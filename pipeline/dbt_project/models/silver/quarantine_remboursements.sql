{{ config(schema='quarantine') }}
{#- Paiements rejetés, tels que reçus (texte brut), avec les règles et motifs, pour décision humaine. -#}
select
    r.id_remboursement,
    r.id_pret,
    r.num_echeance,
    r.date_paiement,
    r.montant_capital,
    r.montant_interets,
    r.montant_total,
    r.canal,
    q.regles,
    q.motifs,
    q.detecte_le
from {{ source('bronze', 'remboursements') }} r
join (
    select
        cle,
        string_agg(regle_id, ', ' order by regle_id) as regles,
        string_agg(motif, ' | ' order by regle_id) as motifs,
        max(detecte_le) as detecte_le
    from {{ source('quality', 'violations') }}
    where table_source = 'remboursements' and action = 'quarantaine'
    group by cle
) q on q.cle = r.id_remboursement
