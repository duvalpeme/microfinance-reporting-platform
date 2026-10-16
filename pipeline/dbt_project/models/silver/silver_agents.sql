select id_agent, code_agence, nom_agent
from {{ source('bronze', 'agents') }}
