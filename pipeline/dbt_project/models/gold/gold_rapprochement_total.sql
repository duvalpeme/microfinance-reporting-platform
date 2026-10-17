{#- Rapprochement au niveau de l'institution : les effets de l'agence INCONNU et des paiements non rattachables
    (prêt inexistant) s'annulent ou s'additionnent ici, ce qui permet de boucler l'écart.

    ecart_brut + effet_quarantaine_total = ecart que la quarantaine n'explique pas.
    Cet écart doit être égal au solde du compte d'attente : c'est là que la comptabilité a parqué ses différences.

    Le bouclage n'est affirmé qu'à la date d'arrêté (BOUCLE / A_EXPLIQUER). Aux dates antérieures le statut est
    INDICATIF : la date d'origine des paiements à date future et des prêts à date de décaissement incohérente
    n'est pas fiable, donc le total ne peut pas y être garanti. -#}
with arrete as (
    select cast(valeur as date) as d from {{ source('bronze', '_meta') }} where cle = 'date_arrete'
),

agences as (
    select
        date_arrete,
        sum(encours_grand_livre) as encours_grand_livre,
        sum(encours_sous_ledger) as encours_sous_ledger
    from {{ ref('gold_rapprochement') }}
    group by 1
),

quar as (
    select
        a.date_arrete,
        sum(abs(try_cast(q.montant_capital as bigint))) as effet_quarantaine_total
    from agences a
    cross join arrete ar
    join {{ ref('quarantine_remboursements') }} q
        on q.regles not like '%REM_02%'
       and (
            (q.regles like '%REM_03%' and a.date_arrete = ar.d)
            or (q.regles not like '%REM_03%' and try_cast(q.date_paiement as date) <= a.date_arrete)
       )
    group by 1
),

attente as (
    select date_arrete, sum(solde) as compte_attente
    from {{ ref('silver_balance_comptable') }}
    where code_poste = 'COMPTE_ATTENTE'
    group by 1
)

select
    a.date_arrete,
    a.encours_grand_livre,
    a.encours_sous_ledger,
    a.encours_grand_livre - a.encours_sous_ledger as ecart_brut,
    coalesce(q.effet_quarantaine_total, 0) as effet_quarantaine_total,
    a.encours_grand_livre - a.encours_sous_ledger + coalesce(q.effet_quarantaine_total, 0) as ecart_a_justifier,
    coalesce(t.compte_attente, 0) as compte_attente,
    a.encours_grand_livre - a.encours_sous_ledger + coalesce(q.effet_quarantaine_total, 0)
        - coalesce(t.compte_attente, 0) as ecart_non_explique,
    case
        when a.date_arrete <> ar.d then 'INDICATIF'
        when abs(a.encours_grand_livre - a.encours_sous_ledger + coalesce(q.effet_quarantaine_total, 0)
                 - coalesce(t.compte_attente, 0)) <= 1000 then 'BOUCLE'
        else 'A_EXPLIQUER'
    end as statut
from agences a
cross join arrete ar
left join quar q on q.date_arrete = a.date_arrete
left join attente t on t.date_arrete = a.date_arrete
order by a.date_arrete desc
