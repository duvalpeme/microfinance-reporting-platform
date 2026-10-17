{#- Rapprochement portefeuille / comptabilité, par agence, pour les derniers arrêtés mensuels.

    encours_grand_livre : comptes de crédits de la balance (sains + en souffrance + litigieux)
    encours_sous_ledger : décaissements - capital remboursé, recalculés depuis les prêts et paiements silver
    effet_quarantaine   : capital des paiements en quarantaine qui sont de VRAIS paiements (négatifs, date future)
                          et rattachables à un prêt ; ils manquent au sous-ledger et gonflent son encours.
                          Les copies de paiements en double sont ignorées : l'original reste dans le silver.
    ecart_apres_quarantaine : ce qui reste à justifier une fois l'effet de la quarantaine neutralisé.

    incertitude_dates : encours des prêts à date de décaissement incohérente (PRE_01) présents dans le sous-ledger.
                        Leur vraie date est inconnue : à une date antérieure à l'arrêté, ils ont pu être placés trop
                        tôt dans le temps, ce qui peut suffire à expliquer un écart. Nulle à l'arrêté (tous décaissés).

    Un paiement à date future n'a plus sa date d'origine : on ne le rapproche qu'à la date d'arrêté.
    L'agence INCONNU reçoit des encours que la comptabilité place dans leur vraie agence : elle est à répartir. -#}
with arrete as (
    select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete'
),

dates as (
    select distinct date_arrete as d
    from {{ ref('silver_balance_comptable') }}
    order by d desc
    limit {{ var('nb_dates_rapprochement') }}
),

gl as (
    select date_arrete as d, code_agence, sum(solde) as encours_grand_livre
    from {{ ref('silver_balance_comptable') }}
    where code_poste in ('CRD_SAINS', 'CRD_DOUTEUX', 'CRD_LITIGIEUX')
      and date_arrete in (select d from dates)
    group by 1, 2
),

cap as (
    select dt.d, r.id_pret, sum(r.montant_capital) as k
    from dates dt
    join {{ ref('silver_remboursements') }} r on r.date_paiement <= dt.d
    group by 1, 2
),

sl as (
    {#- Date effective de décaissement = la plus tardive de la date saisie et de la date d'adhésion du client :
        un prêt ne peut pas être décaissé avant l'adhésion (règle PRE_01). Sans cette borne, un prêt à date
        corrompue entrerait dans le sous-ledger avant sa vraie date. Cette borne ne suffit pas toujours : voir
        incertitude_dates ci-dessous. -#}
    select dt.d, c.code_agence, sum(p.montant_decaisse - coalesce(cap.k, 0)) as encours_sous_ledger
    from dates dt
    join {{ ref('silver_prets') }} p on true
    join {{ ref('silver_clients') }} c on c.id_client = p.id_client
    left join cap on cap.d = dt.d and cap.id_pret = p.id_pret
    where greatest(p.date_decaissement, c.date_adhesion) <= dt.d
    group by 1, 2
),

incert as (
    select dt.d, c.code_agence, sum(p.montant_decaisse - coalesce(cap.k, 0)) as incertitude_dates
    from dates dt
    cross join arrete a
    join {{ ref('silver_prets') }} p on p.dq_regles like '%PRE_01%'
    join {{ ref('silver_clients') }} c on c.id_client = p.id_client
    left join cap on cap.d = dt.d and cap.id_pret = p.id_pret
    where greatest(p.date_decaissement, c.date_adhesion) <= dt.d and dt.d <> a.d
    group by 1, 2
),

quar as (
    select dt.d, c.code_agence, sum(abs(try_cast(q.montant_capital as bigint))) as effet_quarantaine
    from dates dt
    cross join arrete a
    join {{ ref('quarantine_remboursements') }} q
        on q.regles not like '%REM_02%'
       and (
            (q.regles like '%REM_03%' and dt.d = a.d)
            or (q.regles not like '%REM_03%' and try_cast(q.date_paiement as date) <= dt.d)
       )
    join {{ ref('silver_prets') }} p on p.id_pret = q.id_pret
    join {{ ref('silver_clients') }} c on c.id_client = p.id_client
    group by 1, 2
),

joint as (
    select
        coalesce(gl.d, sl.d) as date_arrete,
        coalesce(gl.code_agence, sl.code_agence) as code_agence,
        coalesce(gl.encours_grand_livre, 0) as encours_grand_livre,
        coalesce(sl.encours_sous_ledger, 0) as encours_sous_ledger
    from gl
    full join sl on sl.d = gl.d and sl.code_agence = gl.code_agence
)

select
    j.date_arrete,
    j.code_agence,
    j.encours_grand_livre,
    j.encours_sous_ledger,
    j.encours_grand_livre - j.encours_sous_ledger as ecart_brut,
    coalesce(q.effet_quarantaine, 0) as effet_quarantaine,
    j.encours_grand_livre - j.encours_sous_ledger + coalesce(q.effet_quarantaine, 0) as ecart_apres_quarantaine,
    round({{ var('seuil_ecart_rapprochement') }} * j.encours_grand_livre) as seuil_tolerance,
    coalesce(i.incertitude_dates, 0) as incertitude_dates,
    case
        when j.code_agence = 'INCONNU' then 'A_REPARTIR'
        when abs(j.encours_grand_livre - j.encours_sous_ledger + coalesce(q.effet_quarantaine, 0))
             <= {{ var('seuil_ecart_rapprochement') }} * j.encours_grand_livre then 'CONFORME'
        when abs(j.encours_grand_livre - j.encours_sous_ledger + coalesce(q.effet_quarantaine, 0))
             <= {{ var('seuil_ecart_rapprochement') }} * j.encours_grand_livre + coalesce(i.incertitude_dates, 0) then 'INCERTAIN'
        else 'ECART_A_JUSTIFIER'
    end as statut
from joint j
left join quar q on q.d = j.date_arrete and q.code_agence = j.code_agence
left join incert i on i.d = j.date_arrete and i.code_agence = j.code_agence
order by j.date_arrete desc, j.code_agence
