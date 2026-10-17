-- Pour chaque dimension, les parts d'encours des segments somment à 100 % (à l'arrondi près).
select dimension, sum(part_encours) as total_parts
from {{ ref('gold_concentration') }}
group by 1
having abs(sum(part_encours) - 1) > 0.001
