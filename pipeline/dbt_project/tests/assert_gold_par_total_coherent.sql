-- La ligne TOTAL du PAR est la somme des agences ; les ratios restent entre 0 et 1 ; PAR1 >= PAR30 >= PAR90.
select code_agence
from {{ ref('gold_par_agence') }}
where par30 < 0 or par30 > 1
   or par1 < par30 or par30 < par90
union all
select 'TOTAL_INCOHERENT'
where (select encours_total from {{ ref('gold_par_agence') }} where code_agence = 'TOTAL')
   <> (select sum(encours_total) from {{ ref('gold_par_agence') }} where code_agence <> 'TOTAL')
