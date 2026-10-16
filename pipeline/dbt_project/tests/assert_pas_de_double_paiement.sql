-- Aucun paiement identique (même prêt, échéance, date, montants, canal) en silver.
select id_pret, num_echeance, date_paiement, montant_capital, montant_interets, canal, count(*) as nb
from {{ ref('silver_remboursements') }}
group by all
having count(*) > 1
