# Saisie Comptable SYSCOHADA — application Windows autonome

Application de bureau (Tkinter) qui reproduit les fonctions essentielles
du classeur Excel : Saisie des écritures, Balance, Compte de résultat et
Bilan, calculés automatiquement. Aucune installation d'Excel n'est requise :
une fois compilée, c'est un simple `.exe`.

Le plan comptable intégré (`plan_comptable.json`) est celui importé depuis
votre export Sage (1591 comptes).

## Important : je ne peux pas produire le .exe moi-même

Un `.exe` est un binaire Windows. Je travaille dans un environnement Linux
qui ne peut pas compiler de binaire Windows. La solution ci-dessous utilise
**GitHub Actions** : GitHub compile lui-même le `.exe` sur une machine
Windows à chaque fois que vous poussez du code — c'est la manière standard
et fiable de faire, sans avoir besoin d'un PC Windows.

## Mise en ligne sur GitHub (une seule fois)

```bash
cd accounting-app
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/VOTRE-COMPTE/VOTRE-DEPOT.git
git push -u origin main
```

## Récupérer le .exe

1. Sur GitHub, ouvrez l'onglet **Actions** de votre dépôt : le workflow
   « Build Windows .exe » se déclenche automatiquement à chaque push sur
   `main` (ou lancez-le manuellement via **Run workflow**).
2. Une fois le job terminé (~2-3 minutes), ouvrez son résumé et téléchargez
   l'artifact **SaisieComptable-windows** : il contient `SaisieComptable.exe`.
3. Pour publier une **Release** téléchargeable en un clic (recommandé pour
   partager l'app), créez un tag :
   ```bash
   git tag v1.0
   git push origin v1.0
   ```
   Le `.exe` sera automatiquement attaché à la Release correspondante.

## Utilisation de l'application

- **Saisie** : formulaire d'ajout/modification/suppression d'écritures
  (Date, Pièce, Journal, Compte, Tiers, Libellé, Débit, Crédit, Code flux,
  Code analytique). Le champ **N° Compte** est une liste déroulante avec
  recherche : tapez un numéro ou un mot du libellé (ex. `clients`, `601`,
  `banque`) et choisissez le compte dans la liste qui s'affiche. Le
  **Journal** propose AC/VE/OD/BQ/CA (modifiable librement), et le
  **Code flux** est une liste fermée EXP/INV/FIN pour éviter les fautes de
  frappe. Le libellé du compte s'affiche automatiquement pendant la saisie.

  **Import massif (.xlsx)** *(nouveau)* : pour les volumes d'écritures
  importants, deux boutons sont disponibles au-dessus du tableau :
  - **« Télécharger un modèle (.xlsx) »** : génère un fichier vierge avec
    les bons en-têtes (Date, N° Pièce, Journal, N° Compte, Tiers, Libellé,
    Débit, Crédit, Code flux, Code analytique) et deux lignes d'exemple.
  - **« Importer des écritures (.xlsx) »** : sélectionnez votre fichier
    préparé (l'ordre des colonnes n'a pas d'importance, les en-têtes sont
    reconnus automatiquement) — toutes les lignes sont ajoutées à la
    Saisie en une fois. Les dates peuvent être au format texte (AAAA-MM-JJ)
    ou en dates Excel natives. Les lignes vides sont ignorées ; un compte
    absent du plan comptable ou un montant non numérique déclenche un
    avertissement (la ligne est quand même importée, avec le montant
    invalide remplacé par 0) plutôt que de faire échouer tout l'import.
- **Balance** : synthèse Débit/Crédit/Solde par compte, actualisée à la volée.
- **Compte de résultat** et **Bilan** : calculés automatiquement selon la
  même logique que le classeur Excel (mêmes regroupements de comptes).

Les données sont stockées localement dans :
`%LOCALAPPDATA%\SaisieComptable\comptabilite.db` (SQLite). Elles persistent
d'un lancement à l'autre de l'application.

## Développer / tester en local (optionnel)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Navigation

L'application n'a plus d'onglets classiques : la navigation se fait
entièrement via **la barre de menu** en haut de la fenêtre, avec 5 menus
principaux (en gras) :

- **SAISIE** : Saisie des écritures, Soldes d'ouverture.
- **COMMERCE** : Ventes, Clients, Recouvrement, Facturation, Stocks, Marges bénéficiaires.

### Module Facturation (nouveau)

L'onglet **Facturation** présente directement une facture éditable :
- **En-tête modifiable** et **pied de page modifiable** (texte libre).
- **N° Facture**, **Date**, **Client** (obligatoirement rattaché à un compte
  racine 41, avec la même recherche/validation que dans le reste de l'app).
- **Taux de TVA paramétrable** (compte 44 — 443100 « T.V.A. facturée sur
  ventes »), avec une valeur par défaut mémorisée d'une facture à l'autre.
- **Lignes de vente** liées à un compte de classe **70** (Ventes) : chaque
  ligne a un compte, un libellé, une quantité et un prix unitaire ; le
  montant HT est calculé automatiquement.

**Bouton « Valider et envoyer en Saisie »** : génère automatiquement les
écritures comptables équilibrées dans l'onglet Saisie :
- Débit **Client** (411000) pour le montant TTC.
- Crédit chaque **compte de vente** (70x) pour le HT de sa ligne.
- Crédit **TVA facturée** (443100) pour la taxe.
- **Mise à jour automatique des stocks** : les comptes 701000 (marchandises,
  stock 310000) et 702000 (produits finis, stock 360000) déclenchent en plus
  une sortie de stock au coût unitaire moyen réel (Débit 603100 ou 736000 /
  Crédit le compte de stock correspondant) — les comptes de services
  (ex. 706000) n'impactent aucun stock. Ce mapping compte-de-vente ↔ stock
  est défini dans `core.VENTE_STOCK_MAPPING` (extensible).

Une fois validée, une facture est **verrouillée** (plus de modification
possible, cohérent avec le fait que ses écritures existent déjà en Saisie).

**Bug de calcul du Résultat corrigé au passage** : les comptes de variation
de stock (603100 pour les marchandises, 736000 pour les produits finis)
n'étaient référencés dans aucune formule du Compte de résultat, ce qui
créait un écart Actif/Passif après une vente de marchandises ou de produits
finis. Testé et corrigé : un scénario complet (service + marchandise +
produit fini + TVA) donne désormais un Bilan parfaitement équilibré et un
Résultat net exact (vérifié à l'unité près sur plusieurs cas).

- **PRODUCTION** : Matières premières, Fabrication, Produits finis.

### Module Fabrication — nomenclature et coût de production (nouveau)

L'onglet **Fabrication** contient maintenant deux sous-onglets :

**« Recettes / Coût de production »** *(nouveau)* — un calculateur de coût de
revient (nomenclature / BOM) :
- Créez un **produit fini** (code, nom).
- Ajoutez ses composants : **matières premières** (choisies parmi les
  comptes de stock — le coût unitaire réel est repris automatiquement du
  **coût unitaire moyen** calculé dans l'onglet Stocks, donc directement
  depuis vos achats comptabilisés), **main-d'œuvre** et **énergie** (coût
  unitaire saisi manuellement), avec une quantité pour chacun.
- Le **coût de production total**, le **coût de production unitaire**
  (divisé par la quantité produite par la recette) sont calculés
  automatiquement.
- Réglez une **marge (%)** : le **prix de vente unitaire suggéré** est
  calculé automatiquement (coût de production × (1 + marge)).

Testé avec un cas concret : achat de 100 unités de matière première pour
500 000 (coût unitaire réel 5 000, repris automatiquement des stocks) → une
recette combinant 2 unités de cette matière + main-d'œuvre (3 000) +
énergie (500) donne un coût de production de 13 500, et un prix de vente
suggéré de 18 900 à 40 % de marge.

**« Coûts de fabrication (période) »** — l'ancien contenu de l'onglet
Fabrication (coûts réels de la période via l'axe analytique AN-FAB),
inchangé et toujours disponible.

- **ENGAGEMENTS-PROJETS** : Achats, Fournisseurs, Contrats.

### Module Commerce — Clients / Ventes / Recouvrement (nouveau)

- **Clients** : liste auxiliaire (fiche par client : raison sociale, contact,
  délai de paiement par défaut en jours). Créer / modifier / supprimer, ou
  **importer en masse (.xlsx)** avec un modèle téléchargeable.
- **Ventes** : soldes des opérations avec chaque client (Débit − Crédit sur
  les comptes 411xxx qui lui sont tagués), **total par client**, avec un
  **filtre de plage de dates** (Du / Au). Positif = montant restant dû par
  le client (à recouvrer).
- **Recouvrement** : journal des factures émises à chaque client. À la
  création, l'échéance de **paiement** est calculée automatiquement (date
  de facture + délai par défaut du client). Renseignez ensuite la date
  réelle de paiement au fur et à mesure des encaissements : les **retards
  sont détectés et affichés en rouge** (« EN RETARD (n j) » si l'échéance
  est dépassée sans paiement enregistré, ou « Payé (retard n j) » une fois
  la date réelle enregistrée après l'échéance).

**Saisie** : un nouveau champ **« Client »** (liste déroulante avec
recherche, proposition de création si le code n'existe pas) permet de taguer
chaque écriture — c'est ce qui alimente automatiquement les modules Ventes
et Recouvrement.

### Module Engagements-Projets (nouveau, remplace les placeholders)

- **Fournisseurs** : liste auxiliaire (fiche par fournisseur : raison sociale,
  contact, délais par défaut de paiement et de livraison en jours). Créer /
  modifier / supprimer, ou **importer en masse (.xlsx)** avec un modèle
  téléchargeable.
- **Achats** : soldes des opérations avec chaque fournisseur (Débit − Crédit
  sur les comptes 401xxx/408xxx qui lui sont tagués), **total par
  fournisseur**, avec un **filtre de plage de dates** (Du / Au).
- **Contrats** : journal des commandes passées avec chaque fournisseur. À la
  création, les échéances de **livraison** et de **paiement** sont calculées
  automatiquement (date de commande + délais par défaut du fournisseur).
  Renseignez ensuite les dates réelles de livraison/paiement au fur et à
  mesure : les **dépassements sont détectés et affichés en rouge**
  (« EN RETARD (n j) » si la date prévue est dépassée sans qu'une date
  réelle ait été saisie, ou « Livré/Payé (retard n j) » une fois la date
  réelle enregistrée après l'échéance).

**Saisie** : un nouveau champ **« Fournisseur »** (liste déroulante avec
recherche, proposition de création si le code n'existe pas) permet de taguer
chaque écriture — c'est ce qui alimente automatiquement les modules Achats
et Contrats.

- **ÉTATS ET RAPPORTS** : Grand livre, Balance, Bilan, Compte de résultat,
  TFT, Liasse fiscale, Tableaux d'exécution budgétaire, Impôts,
  Déclarations sociales, Rapprochements bancaires.

Cliquer sur un menu ouvre la liste de ses pages ; cliquer sur une page
l'affiche dans la fenêtre (un seul panneau à la fois).

### Saisie : nouveaux champs (mise à jour)

Le champ « Code flux » a été retiré du formulaire de Saisie. À la place,
chaque écriture propose désormais : **Code analytique**, **Code
budgétaire**, **Code bailleur** (texte libre, pour le suivi par projet/
bailleur de fonds) et **Quantité** (pour la valorisation des stocks — voir
ci-dessous). Le tableau et l'import massif (.xlsx) ont été mis à jour en
conséquence.

⚠️ Le TFT (Tableau des flux de trésorerie) utilisait le Code flux pour
classer les mouvements de trésorerie en EXP/INV/FIN. Ce champ n'étant plus
saisissable, les nouveaux mouvements apparaîtront tous en « Flux non
classés ». Dites-moi si vous voulez qu'on prévoie un autre moyen de les
classer.

**Stocks** (mise à jour) : suivi désormais en **valeur ET en quantité**.
Renseignez la quantité sur chaque écriture touchant un compte de stock
(Saisie), et une quantité initiale (bouton dédié dans l'onglet Stocks) —
l'application calcule alors le **coût unitaire moyen** (valeur du stock
final / quantité finale) pour chaque compte.

### Partie double vraiment forcée (mise à jour majeure)

Le formulaire de Saisie a changé de logique : au lieu d'une ligne à la fois
(un compte + Débit ou Crédit), il demande maintenant **ensemble** :
**Compte débiteur**, **Compte créditeur** et **Montant**. Cliquer sur
« Ajouter » crée automatiquement les deux lignes en une seule opération —
**il est structurellement impossible de créer une écriture déséquilibrée**
par ce formulaire (le compte débiteur doit être différent du compte
créditeur, le montant doit être positif, sinon le logiciel refuse).

Les deux champs comptes sont des listes déroulantes avec recherche ; si
vous quittez le champ avec un code qui n'existe pas dans le Plan comptable,
l'application vous demande de le créer (avec un libellé) avant de continuer
— impossible d'enregistrer une écriture sur un compte invalide.

**Modifier une ligne existante** : sélectionnez-la dans le tableau (chaque
ligne du tableau reste une moitié débit ou crédit, comme avant) — le
formulaire ne pré-remplit alors que le côté concerné ; ne renseignez que ce
compte-là pour la modifier.

**Pour les écritures à plus de 2 comptes** (ex. une facture avec TVA
répartie sur 3 lignes) : ajoutez plusieurs paires successives sur la même
pièce (le N° Pièce reste rempli après chaque « Ajouter » pour faciliter
l'enchaînement) — chaque paire est déjà équilibrée, donc la pièce entière
le reste automatiquement.

### Exercices comptables et clôture annuelle (nouveau)

Une barre en haut de la fenêtre affiche en permanence l'**exercice
comptable en cours** (ex. 2025), avec un sélecteur pour basculer entre
exercices et un bouton **« + Nouvel exercice »**.

Tous les calculs (Saisie, Balance, Bilan, Compte de résultat, TFT, Stocks,
Production, Liasse fiscale) sont désormais **scopés à l'exercice
sélectionné** : seules les écritures datées de cet exercice sont prises en
compte pour les mouvements, et les soldes d'ouverture sont ceux enregistrés
pour cet exercice précis.

**Clôture annuelle** (menu PARAMÈTRES → Exercices comptables) :
- calcule le solde de clôture de chaque compte de bilan (classes 1 à 5) de
  l'exercice sélectionné ;
- intègre le résultat net de l'exercice dans le compte **121000** (Report à
  nouveau créditeur) ;
- reporte ces soldes comme **soldes d'ouverture de l'exercice suivant**
  (créé automatiquement s'il n'existait pas) ;
- **verrouille l'exercice clôturé** : impossible d'ajouter, modifier ou
  supprimer une écriture datée de cet exercice tant qu'il reste clôturé.

Testé avec un cycle complet : exercice 2024 (capital, ventes, achats) →
clôture → exercice 2025 hérite automatiquement des bons soldes d'ouverture
(clients, fournisseurs, banque, report à nouveau incluant le résultat 2024)
et le Bilan reste équilibré, y compris après de nouveaux mouvements en 2025.

### Menu PARAMÈTRES (remplace les plans dans SAISIE)

Les 4 écrans de gestion des plans (Plan comptable, Plan analytique, Plan
budgétaire, Plan bailleurs de fonds) ainsi que les **Exercices comptables**
sont désormais regroupés dans le menu **PARAMÈTRES**.

### Racines des comptes (nouveau)

Chaque compte du Plan comptable est désormais rattaché à une **racine**,
visible dans l'onglet Plan comptable (colonnes « Racine » et « Libellé de la
racine ») :
- **1 chiffre** pour les classes 1, 2, 3, 5, 6, 7, 8, 9.
- **2 chiffres pour la classe 4** (comptes de tiers), qui se subdivise en
  **40** (Fournisseurs et comptes rattachés), **41** (Clients et comptes
  rattachés), 42 (Personnel), 43 (Organismes sociaux), 44 (État), 45
  (Organismes internationaux), 46 (Associés/Groupe), 47 (Débiteurs/
  créditeurs divers), 48 (Régularisations), 49 (Dépréciations sur tiers).

**Les comptes racines existent désormais réellement dans le Plan comptable**
(1, 2, 3, 5, 6, 7, 8, 9, 40 à 49), avec un libellé entre tirets (ex. « —
Fournisseurs et comptes rattachés — ») pour les repérer facilement. Grâce au
tri alphabétique des codes, chaque racine **apparaît en tête de son groupe**
dans toutes les listes de comptes (ex. le compte « 1 » avant 101000, 101100,
etc. ; le compte « 40 » avant 400000, 401000, 401100...).

Les fiches auxiliaires créées dans **Fournisseurs** sont rattachées à la
racine **40**, celles créées dans **Clients** à la racine **41**.

**Sélection du tiers rendue obligatoire (nouveau)** : dans l'onglet Saisie,
si vous tapez directement le compte racine **40** ou **41** dans « Compte
débiteur »/« Compte créditeur », l'application vous avertit qu'on ne saisit
jamais directement sur une racine de regroupement, bascule automatiquement
sur le compte de détail usuel (401000/411000), et impose de choisir le
fournisseur ou le client dans le champ correspondant. Plus largement, **toute
écriture sur un compte de la racine 40 sans fournisseur renseigné (ou de la
racine 41 sans client renseigné) est bloquée** à l'enregistrement.

**Tous les calculs liés aux comptes de tiers ont été mis à jour en
conséquence** :
- Le **Bilan** classe désormais les comptes de tiers **par racine** plutôt
  que par simple signe du solde : la racine 41 (Clients) va toujours en
  Créances, la racine 40 (Fournisseurs) toujours en Dettes circulantes ; les
  autres racines (42 à 49) restent classées par signe, car leur nature
  actif/passif dépend réellement du solde.
- **Achats** et **Ventes** utilisent désormais la racine complète (`40%` et
  `41%`) au lieu de motifs partiels — un **bug a été corrigé au passage** :
  l'ancien filtre (401xxx/408xxx pour les fournisseurs, 411xxx pour les
  clients) ratait des comptes comme 402, 404, 409, 412, 413, 418, 419, qui
  sont maintenant bien pris en compte.

Testé de bout en bout : Bilan équilibré avec un compte fournisseur débiteur
(avance, compte 409xxx) et un compte client sur un effet à recevoir (compte
412xxx), tous deux désormais correctement classés ; comptes racines vérifiés
existants et correctement triés (« 1 » avant 101000, « 40 » avant 400000-
409xxx) ; écriture réelle avec fournisseur tagué toujours cohérente.

### Gestion des plans (détail des écrans)

Le menu **SAISIE** contient maintenant 4 écrans pour créer/modifier/
supprimer les référentiels utilisés lors de la saisie : **Plan comptable**,
**Plan analytique**, **Plan budgétaire** (avec montant prévu), **Plan
bailleurs de fonds**.

### (Ancien mécanisme remplacé)

L'équilibrage « après coup » ligne par ligne a été remplacé par le
formulaire Compte débiteur / Compte créditeur décrit plus haut, qui
équilibre chaque écriture dès sa création plutôt que de le vérifier après.

### Listes déroulantes avec proposition de création (nouveau)

Les champs **Code analytique**, **Code budgétaire** et **Code bailleur**
sont des listes déroulantes alimentées par leurs plans respectifs. Si vous
tapez un code qui n'existe pas encore, l'application vous demande de
confirmer sa création (avec un libellé) avant de passer à la cellule
suivante — impossible d'enregistrer un code orphelin par erreur de frappe.

### Ce qui est pleinement fonctionnel


Saisie, Soldes d'ouverture, Stocks (partagé entre Matières premières et
Produits finis pour l'instant), Fabrication, Compte de résultat, TFT, Grand
livre, Balance, Bilan, Liasse fiscale — ainsi que 3 nouvelles pages basées
sur vos écritures existantes :
- **Ventes** / **Achats** : synthèse des comptes de vente (classe 7) et
  d'achat (classe 6), hors éléments financiers.
- **Marges bénéficiaires** : marge commerciale, valeur ajoutée, résultat
  d'exploitation et résultat net (mêmes calculs que la Liasse fiscale).
- **Clients** / **Fournisseurs** : Grand livre pré-filtré sur les comptes
  411000 / 401000.

### Ce qui reste à construire

**Contrats**, **Tableaux d'exécution budgétaire**, **Impôts**,
**Déclarations sociales** et **Rapprochements bancaires** apparaissent dans
le menu mais affichent pour l'instant un message « fonctionnalité pas
encore développée » — ce sont de nouveaux modules à part entière (suivi de
contrats, calcul d'impôts, etc.) qui nécessitent d'être conçus et développés
spécifiquement. Dites-moi lesquels prioriser.

- **Soldes d'ouverture** *(nouveau)* : saisissez le solde de report à nouveau
  de chaque compte de bilan au 1er jour de l'exercice (= solde de clôture de
  l'exercice précédent). Convention : débiteur = positif, créditeur = négatif.
  La somme de tous les soldes d'ouverture doit être nulle (partie double) —
  un contrôle l'affiche en bas de l'onglet. **Tous les calculs (Balance,
  Bilan, TFT, Liasse fiscale) intègrent désormais automatiquement ces soldes
  d'ouverture** : Balance de clôture = Solde d'ouverture + Mouvements de
  l'exercice. C'est ce qui permet au Bilan de s'équilibrer même si ce n'est
  pas la première année d'activité.
- **Balance** *(mise à jour)* : affiche maintenant, pour chaque compte, le
  Solde d'ouverture, le Débit/Crédit/Solde de la période, et le **Solde de
  clôture**.
- **Stocks** : le stock initial saisi ici alimente désormais directement la
  table des soldes d'ouverture (même mécanisme que ci-dessus).
- **TFT** : la trésorerie d'ouverture est calculée **automatiquement** à
  partir des soldes d'ouverture des comptes de trésorerie (521000/531000/
  570000/585000) ; un bouton permet de la forcer manuellement si besoin.
  Codez `FLUX-EXP`, `FLUX-INV` ou `FLUX-FIN` dans le champ « Code flux » des
  écritures de trésorerie dans l'onglet Saisie pour classer les mouvements.
- **Grand livre** : tapez un N° Compte (liste déroulante avec recherche)
  puis « Afficher » pour voir le détail chronologique et le solde cumulé.
- **Production** : tapez `AN-FAB` dans le champ « Code analytique » de
  l'onglet Saisie sur les lignes de charges de fabrication pour qu'elles
  remontent dans l'onglet Production.

### Liasse fiscale *(mise à jour majeure)*

Renseignez l'identification de l'entité (dénomination, adresse, N° IFU,
exercice clos le...), puis « Exporter la liasse fiscale complète (.xlsx) ».

Le fichier généré reprend **les 92 pages et les mêmes dimensions exactes du
modèle SYSCOHADA système normal que vous avez fourni** (COUVERTURE, BILAN,
RESULTAT, TFT, 39 notes annexes NOTE 1 à NOTE 39, ~20 tableaux fiscaux DGI
SUPPL1 à SUPPL20, fiches R1-R4, etc.) :

- ✅ **BILAN et RESULTAT** : remplis automatiquement depuis vos écritures,
  avec les mêmes codes officiels (AD/AE/AI... côté actif, CA/CJ/DA... côté
  passif, TA/RA/XA... au compte de résultat). Les totaux et le Résultat net
  utilisent désormais la **balance de clôture** (soldes d'ouverture +
  mouvements) — le Bilan s'équilibre toujours, y compris les années
  suivantes une fois les soldes d'ouverture saisis.
- ✅ **TFT** : la page officielle (méthode indirecte avec CAFG) est laissée
  vierge — nous ne calculons pas la CAFG automatiquement. Un onglet
  supplémentaire **« TFT (simplifie) »** est ajouté avec un calcul en
  méthode directe (Ouverture, EXP/INV/FIN, Clôture), cohérent avec la
  Balance.
- ⚠️ **Détail des lignes du Bilan** (AE à AN, CA à CM, DA à DM) : réparti
  par plage de comptes, y compris une répartition proportionnelle des
  amortissements entre catégories — indicatif, à vérifier.
- 📄 **Toutes les autres pages** (39 notes, ~20 tableaux DGI) : conservées
  avec leur mise en page, leurs libellés et **leurs dimensions identiques**
  au modèle fourni, mais les montants qu'elles contenaient (qui sont les
  chiffres 2023 de l'entreprise du modèle, pas les vôtres) sont **effacés**
  pour éviter toute confusion — à compléter manuellement ou par votre
  expert-comptable.

**À faire vérifier par un expert-comptable avant tout dépôt officiel auprès
de la DGI** — cet export est une aide à la préparation, pas un dépôt
directement utilisable tel quel.

## Limites de cette version par rapport au classeur Excel

Cette version ne reprend pas encore le suivi budgétaire / analytique par
projet / par bailleur de fonds (feuille « Rapport d'exécution » du
classeur), ni les comptes auxiliaires Fournisseurs/Clients détaillés.
Dites-moi si vous voulez que je les ajoute — le moteur (`core.py`) est
structuré pour que ce soit un ajout incrémental, pas une réécriture.
