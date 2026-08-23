# RÉSUMÉ POUR NOUVELLE CONVERSATION — Application SYSCOHADA

## À FAIRE EN PREMIER dans la nouvelle conversation
Donner ce fichier ZIP complet à Claude et dire : « Voici mon projet, lis
RESUME_MIGRATION.md pour te mettre à jour, puis continue le travail. »

---

## CE QU'EST LE PROJET

Application de comptabilité SYSCOHADA (Burkina Faso), en Python/Tkinter,
avec 3 programmes :
1. **`main.py`** → compile en `SaisieComptable.exe` — application de
   bureau autonome (ouvre directement une base SQLite locale).
2. **`server.py`** → compile en `SaisieComptableServeur.exe` — serveur
   réseau (HTTP/JSON, bibliothèque standard uniquement) qui expose la
   même base de données pour un accès multi-utilisateur simultané.
3. **`client_main.py`** → compile en `SaisieComptableClient.exe` —
   application de bureau séparée qui se connecte au serveur par réseau
   (LAN ou Internet), sans jamais toucher de fichier local.

`core.py` (~8500 lignes) contient tout le moteur métier (comptabilité,
GRH, achats, ventes, stocks, immobilisations, GRH, trésorerie...),
partagé par les 3 programmes. `client_core.py` est un module miroir qui
transforme les appels `core.py` en requêtes réseau vers le serveur.

Build automatique via GitHub Actions : `.github/workflows/main.yml`
(⚠ le fichier s'appelle **main.yml**, pas build.yml — piège déjà
rencontré). Un seul push déclenche les 3 compilations PyInstaller.

## L'UTILISATEUR — CONTEXTE IMPORTANT

- **Non technique**, a beaucoup de mal avec les manipulations Windows
  (invite de commandes, GitHub, gestion de fichiers). Donner des
  instructions très explicites, étape par étape, sans jargon.
- **Ne veut PAS utiliser Python directement** (a explicitement refusé
  cette option) — reste sur le flux .exe + GitHub Actions.
- A plusieurs dossiers avec des copies éparpillées de l'application sur
  sa machine (COMPTA, COMPTA2, Downloads/SaisieComptable-windows-...) —
  source récurrente de confusion (teste souvent un ancien .exe sans
  s'en rendre compte).
- Port **8765 par défaut bloqué par Windows** sur sa machine (WinError
  10013) — utilise **le port 8080** à la place, systématiquement.

## PROBLÈME RÉCURRENT LE PLUS FRÉQUENT — À VÉRIFIER EN PREMIER

**Symptôme** : "Fonction non autorisée à distance", écran vide sans
erreur, ou tout comportement qui ne correspond pas à ce qui vient d'être
codé → dans 90% des cas, **l'utilisateur teste encore un ancien .exe**,
pas le dernier build.

**Solution mise en place** : `server.py` a une constante
`SERVER_VERSION = "2026-08-23-v1"` (à incrémenter à CHAQUE modification
de server.py — ex. "2026-08-24-v1"), affichée à 3 endroits :
console du serveur au démarrage, bouton "Tester la connexion" du
client, barre du haut du client une fois connecté. **Toujours vérifier
ce numéro avant de chercher un bug ailleurs.**

## ARCHITECTURE DE SÉCURITÉ DU SERVEUR (important, ne pas régresser)

`server.py` utilise un modèle **liste noire** (pas liste blanche) :
`RPC_WHITELIST` est calculée dynamiquement au démarrage (toutes les
fonctions publiques de `core.py` prenant `conn` en premier argument),
moins `RPC_BLOCKLIST` (14 fonctions sensibles : gestion utilisateurs/
niveaux d'accès, `reinitialiser_donnees`, `verify_password`, `init_db`,
etc.) et les fonctions `export_*`/`import_*` (chemins de fichiers
locaux au serveur, sans usage réseau direct). **Ne JAMAIS revenir à une
liste blanche manuelle** — c'est la source du problème ci-dessus,
déjà résolue une fois.

## ÉTAT D'AVANCEMENT — CLIENT RÉSEAU

**Les 48 sous-menus de l'application sont couverts** dans
`client_main.py` (dict `ClientApp.IMPLEMENTED_SCREENS`) :
- 43 écrans pleinement fonctionnels (testés de bout en bout : Saisie,
  GRH complet, Achats, Ventes, Rapports financiers, Trésorerie,
  Immobilisations, Transport, Paramètres...).
- 5 écrans ADMIN sensibles (Utilisateurs, Niveaux d'accès,
  Réinitialisation, Modification factures, Modèle bon de commande)
  affichent une explication claire au lieu d'un écran — volontairement
  réservés à l'application de bureau, par sécurité.

Le filtrage des menus par profil (niveau d'accès) fonctionne sur les
deux applications (bureau ET client) — voir `core.MENU_STRUCTURE`,
`core.get_menus_autorises()`.

**7 profils métier** disponibles (ADMIN > Niveaux d'accès > "Ajouter les
niveaux courants") : Administrateur, Comptable, Vendeur, Chargé des
achats, GRH, Trésorier, Usine — chacun avec des menus adaptés à sa
fonction.

## BUGS MAJEURS DÉJÀ TROUVÉS ET CORRIGÉS (ne pas réintroduire)

1. **`compute_balance()` excluait les comptes absents du Plan comptable
   bundlé** — cause de l'écart Actif/Passif chassé pendant des dizaines
   de messages. Corrigé : parcourt l'union des comptes du Plan
   comptable + soldes d'ouverture + écritures.
2. **Formules `...Nm1`** (N-1) utilisaient un exercice séparé au lieu du
   solde d'ouverture de l'exercice courant — corrigé dans 5 endroits
   (TFT, CR, Situation financière, Bilan gabarit).
3. **PyInstaller + import dynamique** (`importlib.import_module`) ne
   bundle pas le module — toujours utiliser des `import X` littéraux à
   l'intérieur des fonctions, jamais dynamiques.
4. **Le serveur restait figé sur un instantané ancien de la base**
   (WAL, connexion longue durée) — corrigé avec un `conn.commit()`
   avant chaque requête réseau.
5. Workflow GitHub nommé **`main.yml`**, pas `build.yml` — toujours
   utiliser ce nom exact.

## PROCHAINES ÉTAPES POSSIBLES (à demander à l'utilisateur)

- Nettoyage des anciens dossiers/exécutables sur sa machine (en cours
  au moment de cette migration).
- Vérifier que la version 2026-08-23-v1 (ou plus récente) tourne
  correctement une fois le ménage fait.
- Éventuellement : renforcer la sécurité serveur avec une vérification
  par fonction basée sur le niveau d'accès (actuellement, le filtrage
  par profil n'est appliqué que côté client/UI, pas strictement
  contrôlé côté serveur — noté comme limitation acceptée pour un usage
  en réseau de confiance).
- Chiffrement HTTPS du serveur si accès Internet envisagé (actuellement
  HTTP en clair, adapté au LAN de confiance uniquement).

## FICHIERS DU PROJET

```
main.py                    Application de bureau (~9100 lignes)
core.py                    Moteur métier partagé (~8500 lignes)
server.py                  Serveur réseau
client_core.py             Module miroir réseau (proxy RPC générique)
client_main.py             Application client réseau (~3100 lignes)
bilan_template_data.py     Gabarit Bilan encodé en base64
etats_financiers_data.py   Gabarits CR/TFT/Situation financière (base64)
factory_icon_data.py       Icône de l'application (base64)
factory_icon.ico
plan_comptable.json        Plan comptable SYSCOHADA de référence
templates/                 Gabarits Excel bruts (sources des .py base64)
.github/workflows/main.yml Build GitHub Actions (3 exécutables)
requirements.txt
README.md                  Journal DÉTAILLÉ de tout ce qui a été fait
                            (très long — RESUME_MIGRATION.md suffit pour
                            reprendre le travail, README.md sert de
                            référence historique si besoin de détails)
```

## STYLE DE TRAVAIL ATTENDU (déjà établi, à poursuivre)

- Toujours compiler (`python3 -m py_compile`) et tester avec un vrai
  scénario avant de livrer.
- Pour toute modification serveur/client réseau : tester avec un VRAI
  serveur + VRAI client (pas juste le moteur local) — lancer
  `server.py` en arrière-plan, puis appeler via `client_core.py`.
- Toujours vérifier la non-régression du moteur comptable (Bilan
  équilibré) après une modification.
- Toujours repackager le zip complet et le fournir via `present_files`
  après chaque modification.
- Donner des instructions Windows très explicites et simples (l'
  utilisateur n'est pas technique).
