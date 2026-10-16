{#- Prêts typés. Le statut SOLDE sans date de solde est ramené à EN_COURS (PRE_02) ;
    le statut d'origine reste dans statut_source. Le classement CONTENTIEUX est recalculé en gold. -#}
select
    p.id_pret,
    p.id_client,
    p.id_produit,
    p.id_agent,
    try_cast(p.date_decaissement as date) as date_decaissement,
    try_cast(p.montant_decaisse as bigint) as montant_decaisse,
    try_cast(p.taux_annuel as double) as taux_annuel,
    try_cast(p.duree_mois as integer) as duree_mois,
    p.periodicite,
    try_cast(p.frais_dossier as bigint) as frais_dossier,
    try_cast(p.date_fin_prevue as date) as date_fin_prevue,
    case
        when p.statut = 'SOLDE' and p.date_solde is null then 'EN_COURS'
        else p.statut
    end as statut,
    p.statut as statut_source,
    try_cast(p.date_solde as date) as date_solde,
    f.dq_regles
from {{ source('bronze', 'prets') }} p
left join {{ ref('silver_dq_flags') }} f on f.cle = p.id_pret
