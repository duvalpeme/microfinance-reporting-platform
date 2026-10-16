{#- Nettoyage des clients :
    - doublons (CLI_01) : retirés (le plus ancien identifiant est conservé)
    - code agence : normalisé ; si introuvable -> agence technique INCONNU
    - secteur manquant -> NON_RENSEIGNE ; téléphone invalide -> NULL
    Les valeurs d'origine restent consultables en bronze ; dq_regles liste les règles déclenchées. -#}
with b as (
    select
        *,
        upper(replace(replace(trim(code_agence), '-', ''), ' ', '')) as code_norm
    from {{ source('bronze', 'clients') }}
),

doublons as (
    select cle from {{ source('quality', 'violations') }} where regle_id = 'CLI_01_DOUBLON'
)

select
    b.id_client,
    b.type_client,
    upper(trim(b.nom)) as nom,
    trim(b.prenom) as prenom,
    trim(b.raison_sociale) as raison_sociale,
    b.genre,
    try_cast(b.date_naissance as date) as date_naissance,
    case
        when b.type_client = 'INDIVIDUEL' and regexp_matches(b.telephone, '^6[0-9]{8}$') then b.telephone
    end as telephone,
    case
        when b.code_norm in (select code_agence from {{ source('bronze', 'agences') }}) then b.code_norm
        else 'INCONNU'
    end as code_agence,
    b.code_agence as code_agence_source,
    coalesce(nullif(trim(b.secteur_activite), ''), 'NON_RENSEIGNE') as secteur_activite,
    try_cast(b.date_adhesion as date) as date_adhesion,
    f.dq_regles
from b
left join {{ ref('silver_dq_flags') }} f on f.cle = b.id_client
where b.id_client not in (select cle from doublons)
