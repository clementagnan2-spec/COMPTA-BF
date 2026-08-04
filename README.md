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

## Onglets disponibles

Saisie, **Soldes d'ouverture**, Grand livre, Balance, Stocks, Production
(coûts de fabrication), Compte de résultat, Bilan, TFT, **Liasse fiscale**.

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
