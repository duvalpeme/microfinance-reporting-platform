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

## Décisions de conception

- Les paiements négatifs sont mis en quarantaine plutôt que corrigés : erreur de signe et annulation
  sont indiscernables sans décision humaine.
- Les prêts dont la date de décaissement est incohérente sont conservés et marqués, pour ne pas
  retirer d'encours réel du rapprochement comptable.

## Couche gold

- **PAR** : calculé sur l'encours évaluable. Les prêts sans échéancier (règle ECH_01) ne permettent pas de
  calculer un retard : ils sont exclus du dénominateur et leur encours est présenté à part
  (`encours_non_evaluable`).
- **Retard incertain** : un paiement mis en quarantaine (montant négatif, date future) fait apparaître l'échéance
  correspondante comme impayée. Le PAR officiel inclut ces cas ; la colonne `par30_hors_incertain` donne
  la valeur sans eux. Le vrai chiffre se situe entre les deux, tant que la quarantaine n'est pas arbitrée.
- **Barème de provisionnement** : illustratif (voir plus haut). Pas de provisionnement spécifique sur garanties.
- **Fonds propres** : capital + réserves + résultat comptable, sans retraitement prudentiel. Les limites
  réglementaires de division des risques dépendent du texte applicable : elles ne sont pas codées.

## Rapprochement portefeuille / comptabilité

- Au niveau de l'institution, à l'arrêté, l'écart doit être entièrement expliqué par les paiements en quarantaine
  et le solde du compte d'attente. C'est un test dbt : il échoue si un écart reste inexpliqué.
- Par agence, un écart est signalé s'il dépasse 0,5 % de l'encours comptable de l'agence après neutralisation de
  la quarantaine. Ce seuil de matérialité est un paramètre (`seuil_ecart_rapprochement`), non ajusté aux anomalies.
- **Agence INCONNU** : quand le code agence d'un client est irrécupérable, son encours est rattaché à une agence
  technique alors que la comptabilité le place dans sa vraie agence. L'agence réelle ressort avec un écart positif
  qui n'est pas une erreur comptable. Cette ambiguïté peut produire une fausse alerte (observée sur 1 graine sur 5).
- **Dates de décaissement incohérentes (PRE_01)** : à une date antérieure à l'arrêté, un prêt à date corrompue peut
  entrer trop tôt dans le sous-ledger. Un écart que ces prêts peuvent expliquer reçoit le statut INCERTAIN au lieu
  de ECART_A_JUSTIFIER. Cette prudence peut transformer un vrai écart en INCERTAIN (observé sur 1 graine sur 5).
- Aux dates antérieures à l'arrêté, le total est INDICATIF : la date d'origine des paiements à date future et des
  prêts à date incohérente n'est pas fiable, donc le bouclage n'y est pas garanti.
- Mesure sur cinq graines : 14 écarts injectés sur 15 signalés fermement, le quinzième signalé INCERTAIN,
  une fausse alerte. Le seuil n'a pas été réglé pour effacer ces cas.
