-- Une provision est comprise entre 0 et l'encours du prêt.
select id_pret
from {{ ref('gold_encours_pret') }}
where encours > 0 and (provision < 0 or provision > encours)
