-- Un prêt SOLDE doit avoir une date de solde (règle PRE_02 corrigée en silver).
select id_pret
from {{ ref('silver_prets') }}
where statut = 'SOLDE' and date_solde is null
