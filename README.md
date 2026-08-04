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
  (Date, Pièce, Journal, Compte, Tiers, Libellé, Débit, Crédit, Code flux).
  Le libellé du compte s'affiche automatiquement pendant la saisie.
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

Saisie, Grand livre, Balance, Stocks, Production (coûts de fabrication),
Compte de résultat, Bilan, TFT (tableau des flux de trésorerie).

- **Grand livre** : tapez un N° Compte (ex. `411000`) puis « Afficher » pour
  voir le détail chronologique et le solde cumulé.
- **Stocks** : sélectionnez un compte de stock dans le tableau, saisissez
  son stock initial, puis « Enregistrer ».
- **Production** : pour qu'une charge remonte dans les coûts de fabrication,
  tapez `AN-FAB` dans le champ « Code analytique » de l'onglet Saisie sur
  la ligne concernée.
- **TFT** : saisissez la trésorerie d'ouverture, et codez `FLUX-EXP`,
  `FLUX-INV` ou `FLUX-FIN` dans le champ « Code flux » des écritures de
  trésorerie (comptes 521000/531000/570000/585000) dans l'onglet Saisie.

## Limites de cette version par rapport au classeur Excel

Cette version ne reprend pas encore le suivi budgétaire / analytique par
projet / par bailleur de fonds (feuille « Rapport d'exécution » du
classeur), ni les comptes auxiliaires Fournisseurs/Clients détaillés.
Dites-moi si vous voulez que je les ajoute — le moteur (`core.py`) est
structuré pour que ce soit un ajout incrémental, pas une réécriture.
