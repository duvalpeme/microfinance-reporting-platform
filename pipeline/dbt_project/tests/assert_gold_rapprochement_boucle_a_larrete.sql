-- Au niveau de l'institution, à l'arrêté, l'écart entre comptabilité et portefeuille doit être entièrement
-- expliqué : paiements en quarantaine + solde du compte d'attente. Un écart non expliqué fait échouer le test.
select date_arrete, ecart_non_explique
from {{ ref('gold_rapprochement_total') }}
where statut = 'A_EXPLIQUER'
