select compte, code_poste, libelle, classe
from {{ source('bronze', 'plan_comptable') }}
