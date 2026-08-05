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
- **COMMERCE** : Ventes, Clients, Stocks, Marges bénéficiaires.
- **PRODUCTION** : Matières premières, Fabrication, Produits finis.
- **ENGAGEMENTS-PROJETS** : Achats, Fournisseurs, Contrats.
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

### Gestion des plans (nouveau)

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
