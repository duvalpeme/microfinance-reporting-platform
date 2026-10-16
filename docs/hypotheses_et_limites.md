# Hypothèses et limites

Ce projet est une démonstration technique sur **données entièrement synthétiques**.
Il ne reproduit aucune institution réelle et ne constitue pas un outil réglementaire prêt à l'emploi.

## Données

- Toutes les données sont générées par `data/generator/generate_data.py` (graine paramétrable).
- L'historique démarre à la date `--debut` (mise en production fictive du système d'information) :
  le portefeuille se construit à partir de zéro, sans soldes d'ouverture.
- Échéancier mensuel à capital constant, intérêts calculés sur le capital restant dû.
- Les profils de remboursement sont simplifiés : bon payeur, retardataire, paiement partiel avec
  complément tardif, défaillant. Pas de rééchelonnement ni de radiation.

## Référentiel comptable et prudentiel

- Le plan comptable est **simplifié et fictif** : à remplacer par le plan réglementaire applicable
  à la catégorie de l'institution avant tout usage réel.
- Les taux de provisionnement par tranche de retard (1 %, 5 %, 25 %, 50 %, 75 %, 100 %) sont
  **illustratifs**, non issus d'une instruction réglementaire.

## Contrôles qualité

- Le taux de détection est mesuré contre des anomalies **injectées par le projet lui-même** :
  il valide les règles, pas leur performance sur des données réelles, qui seront plus variées.
- La détection des doublons de clients repose sur une clé exacte (nom, prénom, date de naissance,
  téléphone, après normalisation). Un doublon dont l'original a aussi été altéré lui échappe.
  Un rapprochement approximatif (distance d'édition) serait l'amélioration naturelle.
- Le rapprochement portefeuille / comptabilité n'est pas encore couvert : il relève de la couche gold.

## Décisions de conception

- Les paiements négatifs sont mis en quarantaine plutôt que corrigés : erreur de signe et annulation
  sont indiscernables sans décision humaine.
- Les prêts dont la date de décaissement est incohérente sont conservés et marqués, pour ne pas
  retirer d'encours réel du rapprochement comptable.
