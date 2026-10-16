-- Aucun paiement silver ne doit avoir de montant négatif ou incohérent (total = capital + intérêts).
select id_remboursement
from {{ ref('silver_remboursements') }}
where montant_total <= 0
   or montant_capital < 0
   or montant_interets < 0
   or montant_total <> montant_capital + montant_interets
