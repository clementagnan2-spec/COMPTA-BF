# -*- coding: utf-8 -*-
"""
CLIENT — application de bureau qui se connecte à un SERVEUR
(voir server.py) par réseau local ou Internet, pour permettre à
PLUSIEURS UTILISATEURS de travailler EN MÊME TEMPS sur la même base de
données comptable.

Contrairement à main.py (qui ouvre directement un fichier SQLite local),
cette application n'ouvre AUCUN fichier local — toutes les opérations
(saisie, consultation) passent par le réseau via client_core.py.

Premier module entièrement fonctionnel de bout en bout : la SAISIE
COMPTABLE (multi-lignes, avec Bilan de contrôle en temps réel). Les
écrans Ventes / Achats / Stocks du circuit commercial suivent le même
principe (voir client_core.py + server.py RPC_WHITELIST à étendre) et
seront ajoutés en s'appuyant sur cette même architecture.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import core  # fonctions PURES (sans accès base) réutilisées telles quelles : to_display_date, to_iso_date...
import client_core
from client_core import RemoteConnection, RemoteAuthError, RemoteCallError, RemoteConnectionError


def fmt_cfa(v):
    if v in (None, ""):
        return ""
    try:
        return f"{v:,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


APPEL_ECHEC = object()  # sentinelle distincte de None (un appel reussi peut legitimement renvoyer None)


def appeler(widget, remote, fonction, *args, **kwargs):
    """Enveloppe tout appel réseau avec une gestion d'erreur unifiée
    (session expirée, serveur injoignable, erreur métier) — factorisé
    pour être réutilisé par tous les écrans du client (Saisie, GRH...).
    Renvoie APPEL_ECHEC (PAS None) en cas d'échec, pour ne jamais
    confondre un appel réussi qui renvoie légitimement None avec un échec."""
    try:
        return getattr(client_core, fonction)(remote, *args, **kwargs)
    except RemoteAuthError as exc:
        messagebox.showerror("Session expirée", str(exc), parent=widget)
        widget.winfo_toplevel().destroy()
    except RemoteConnectionError as exc:
        messagebox.showerror("Connexion perdue", str(exc), parent=widget)
    except RemoteCallError as exc:
        messagebox.showerror("Erreur", str(exc), parent=widget)
    return APPEL_ECHEC


class LoginWindow(tk.Tk):
    """Écran de connexion : adresse du serveur, port, identifiants —
    premier écran affiché au lancement du client."""

    def __init__(self):
        super().__init__()
        self.title("PLATEFORME INTEGREE DE GESTION — Client")
        self.geometry("460x420")
        self.resizable(False, False)
        try:
            icon_path = core.get_app_icon_path()
            self.iconbitmap(icon_path)
        except Exception:
            pass

        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Connexion au serveur", font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text=(
            "Renseignez l'adresse du poste serveur (sur le réseau local : son adresse IP, ex. "
            "192.168.1.10 — visible avec 'ipconfig' sur le poste serveur)."
        ), foreground="#595959", wraplength=400, justify="left").pack(anchor="w", pady=(0, 16))

        form = ttk.Frame(frame)
        form.pack(fill="x")
        ttk.Label(form, text="Adresse du serveur :").grid(row=0, column=0, sticky="w", pady=4)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(form, textvariable=self.host_var, width=28).grid(row=0, column=1, pady=4, sticky="w")

        ttk.Label(form, text="Port :").grid(row=1, column=0, sticky="w", pady=4)
        self.port_var = tk.StringVar(value="8765")
        ttk.Entry(form, textvariable=self.port_var, width=10).grid(row=1, column=1, pady=4, sticky="w")

        ttk.Label(form, text="Identifiant :").grid(row=2, column=0, sticky="w", pady=4)
        self.user_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.user_var, width=28).grid(row=2, column=1, pady=4, sticky="w")

        ttk.Label(form, text="Mot de passe :").grid(row=3, column=0, sticky="w", pady=4)
        self.pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(form, textvariable=self.pwd_var, width=28, show="•")
        pwd_entry.grid(row=3, column=1, pady=4, sticky="w")
        pwd_entry.bind("<Return>", lambda e: self.connecter())

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, foreground="#B00020", wraplength=400, justify="left").pack(
            anchor="w", pady=(12, 8))

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))
        self.connect_btn = ttk.Button(btns, text="Se connecter", command=self.connecter)
        self.connect_btn.pack(side="left")
        ttk.Button(btns, text="Tester la connexion au serveur", command=self.tester).pack(side="left", padx=8)

        self.remote = None

    def tester(self):
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.status_var.set("Le port doit être un nombre.")
            return
        remote = RemoteConnection(host, port, timeout=5)
        info = remote.ping()
        if info:
            version = info.get("version", "?")
            nb_fn = info.get("nb_fonctions_autorisees", "?")
            self.status_var.set(f"✓ Serveur joignable — version {version} ({nb_fn} fonctions autorisées).")
            self.status_var_color("#1F7A1F")
        else:
            self.status_var.set(f"✗ Serveur injoignable à {host}:{port} — vérifiez l'adresse, le port, et "
                                 f"que le serveur est bien démarré sur l'autre poste.")
            self.status_var_color("#B00020")

    def status_var_color(self, color):
        for w in self.winfo_children():
            pass  # simple — la couleur est déjà fixée à la création du Label ci-dessus

    def connecter(self):
        host = self.host_var.get().strip()
        nom_utilisateur = self.user_var.get().strip()
        mot_de_passe = self.pwd_var.get()
        if not host or not nom_utilisateur or not mot_de_passe:
            self.status_var.set("Adresse du serveur, identifiant et mot de passe sont obligatoires.")
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.status_var.set("Le port doit être un nombre.")
            return

        self.connect_btn.configure(state="disabled")
        self.status_var.set("Connexion en cours…")
        self.update_idletasks()

        remote = RemoteConnection(host, port)
        try:
            remote.login(nom_utilisateur, mot_de_passe)
        except RemoteAuthError as exc:
            self.status_var.set(str(exc))
            self.connect_btn.configure(state="normal")
            return
        except RemoteConnectionError as exc:
            self.status_var.set(str(exc))
            self.connect_btn.configure(state="normal")
            return

        self.remote = remote
        self.destroy()


class ClientApp(tk.Tk):
    """Fenêtre principale du client, une fois connecté — barre de menu
    identique dans l'esprit à l'application de bureau (core.MENU_STRUCTURE),
    filtrée selon les sous-menus autorisés pour le niveau d'accès connecté
    (transmis par le serveur à la connexion). Seul l'écran Saisie est
    pleinement implémenté côté client pour l'instant — les autres
    sous-menus autorisés affichent un message clair plutôt que de planter,
    en attendant leur construction (même modèle à suivre)."""

    # Sous-menus du circuit commercial déjà pleinement fonctionnels côté client.
    IMPLEMENTED_SCREENS = {
        "saisie": lambda parent, remote: RemoteSaisieTab(parent, remote),
        "grh_personnel": lambda parent, remote: RemotePersonnelTab(parent, remote),
        "grh_time_sheet": lambda parent, remote: RemoteTimeSheetTab(parent, remote),
        "grh_kpi": lambda parent, remote: RemoteKpiTab(parent, remote),
        "grh_tableau_bord": lambda parent, remote: RemoteTableauBordGrhTab(parent, remote),
        "grh_hs": lambda parent, remote: RemoteHsTab(parent, remote),
        "fournisseurs": lambda parent, remote: RemoteFournisseursTab(parent, remote),
        "reglements": lambda parent, remote: RemoteReglementsTab(parent, remote),
        "grand_livre": lambda parent, remote: RemoteGrandLivreTab(parent, remote),
        "balance": lambda parent, remote: RemoteBalanceTab(parent, remote),
        "bilan_syscohada": lambda parent, remote: RemoteBilanTab(parent, remote),
        "compte_resultat_sig": lambda parent, remote: RemoteEtatFormuleTab(
            parent, remote, "Compte de résultat (SIG)", "compute_cr"),
        "tft": lambda parent, remote: RemoteEtatFormuleTab(parent, remote, "TFT", "compute_tft_gabarit"),
        "situation_financiere": lambda parent, remote: RemoteEtatFormuleTab(
            parent, remote, "Situation financière", "compute_situation_fin"),
        "clients": lambda parent, remote: RemoteClientsTab(parent, remote),
        "facturation": lambda parent, remote: RemoteFacturationTab(parent, remote),
        "stocks": lambda parent, remote: RemoteStocksTab(parent, remote),
        "tresorerie": lambda parent, remote: RemoteTresorerieTab(parent, remote),
        "immobilisations": lambda parent, remote: RemoteImmobilisationsTab(parent, remote),
        "expression_besoin": lambda parent, remote: RemoteExpressionBesoinTab(parent, remote),
        "ep_bon_commande": lambda parent, remote: RemoteBonCommandeTab(parent, remote),
        "recouvrement": lambda parent, remote: RemoteRecouvrementTab(parent, remote),
        "marges": lambda parent, remote: RemoteMargesTab(parent, remote),
        "contrats": lambda parent, remote: RemoteContratsTab(parent, remote),
        "bordereau_livraison": lambda parent, remote: RemoteBordereauLivraisonTab(parent, remote),
        "amortissements": lambda parent, remote: RemoteAmortissementsTab(parent, remote),
        "transport": lambda parent, remote: RemoteParcAutoTab(parent, remote),
        "missions": lambda parent, remote: RemoteMissionsTab(parent, remote),
        "pieces_rechange": lambda parent, remote: RemotePiecesRechangeTab(parent, remote),
        "reparations": lambda parent, remote: RemoteReparationsTab(parent, remote),
        "plan_analytique": lambda parent, remote: RemoteSimplePlanTab(
            parent, remote, "PLAN ANALYTIQUE", "list_analytic_codes", "add_analytic_code",
            "delete_analytic_code", extra_field="unite"),
        "plan_budgetaire": lambda parent, remote: RemoteSimplePlanTab(
            parent, remote, "PLAN BUDGÉTAIRE", "list_budget_codes", "add_budget_code",
            "delete_budget_code", extra_field="montant"),
        "plan_bailleur": lambda parent, remote: RemoteSimplePlanTab(
            parent, remote, "PLAN BAILLEURS DE FONDS", "list_donor_codes", "add_donor_code",
            "delete_donor_code"),
        "taux_tva": lambda parent, remote: RemoteSimplePlanTab(
            parent, remote, "TAUX DE TVA", "list_taux_tva", "add_taux_tva", "delete_taux_tva",
            extra_field="montant"),
        "taux_retenue": lambda parent, remote: RemoteSimplePlanTab(
            parent, remote, "TAUX DE RETENUE À LA SOURCE", "list_taux_retenue", "add_taux_retenue",
            "delete_taux_retenue", extra_field="montant"),
        "energie": lambda parent, remote: RemoteAnalytiquePeriodeTab(
            parent, remote, "Énergie",
            "Coûts d'énergie (eau, électricité, essence, gasoil, gaz...) par code analytique, sur l'exercice "
            "courant.", "ENERGIE-"),
        "maintenance": lambda parent, remote: RemoteAnalytiquePeriodeTab(
            parent, remote, "Maintenance",
            "Coûts de maintenance (véhicules, bâtiments, machines, informatique...) par code analytique, sur "
            "l'exercice courant.", "MAINT-"),
        "production": lambda parent, remote: RemoteProductionTab(parent, remote),
        "exercices": lambda parent, remote: RemoteExercicesTab(parent, remote),
        "synchronisation": lambda parent, remote: RemoteSynchronisationTab(parent, remote),
        "rapports_technique": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Rapports technique",
            "À définir — dites-moi quels rapports techniques vous voulez ici et je construis l'écran."),
        "ouverture": lambda parent, remote: RemoteOuvertureTab(parent, remote),
        "plan_comptable": lambda parent, remote: RemotePlanComptableTab(parent, remote),
        "admin_factures": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Modification des factures",
            "Réservé à l'application de bureau, par sécurité — modification de factures déjà validées, "
            "opération sensible non exposée à distance pour l'instant."),
        "admin_modele_bon_commande": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Modèle de bon de commande",
            "Réservé à l'application de bureau — édition d'un modèle de document, opération locale au "
            "poste serveur."),
        "niveaux_acces": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Niveaux d'accès",
            "Réservé à l'application de bureau, par sécurité — la gestion des niveaux d'accès et de leurs "
            "autorisations n'est volontairement pas exposée à distance (voir server.py RPC_WHITELIST)."),
        "utilisateurs": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Utilisateurs",
            "Réservé à l'application de bureau, par sécurité — la création/suppression d'utilisateurs "
            "n'est volontairement pas exposée à distance."),
        "reinitialisation": lambda parent, remote: RemotePlaceholderTab(
            parent, remote, "Réinitialisation des données",
            "Réservé à l'application de bureau, par sécurité — opération destructrice et irréversible, "
            "volontairement non exposée à distance."),
    }

    def __init__(self, remote: RemoteConnection):
        super().__init__()
        self.remote = remote
        self.pages = {}
        self.report_callback_exception = self._report_callback_exception
        self.title(f"PLATEFORME INTEGREE DE GESTION — Client — {remote.nom_utilisateur} "
                    f"({remote.niveau_acces}) — {remote.host}:{remote.port}")
        self.geometry("1300x800")
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        try:
            self.iconbitmap(core.get_app_icon_path())
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        top_bar = ttk.Frame(self, relief="raised", padding=4)
        top_bar.pack(fill="x")
        ttk.Label(top_bar, text=f"Connecté : {remote.nom_utilisateur} ({remote.niveau_acces})",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
        ttk.Label(top_bar, text=f"Serveur : {remote.host}:{remote.port}",
                  foreground="#595959").pack(side="left", padx=8)
        try:
            exercice_serveur = client_core.get_current_exercice(remote)
        except Exception:
            exercice_serveur = "?"
        ttk.Label(top_bar, text=f"Exercice comptable (serveur) : {exercice_serveur}",
                  font=("Segoe UI", 9, "bold"), foreground="#B00020").pack(side="left", padx=8)
        ttk.Label(top_bar, text=f"Version serveur : {getattr(remote, 'server_version', '?')}",
                  foreground="#595959").pack(side="left", padx=8)
        ttk.Button(top_bar, text="Se déconnecter", command=self._on_close).pack(side="right", padx=8)

        self._build_menu()

        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # Ouvre le premier sous-menu autorisé et implémenté par défaut
        # (généralement la Saisie), sinon un message d'accueil.
        premiere_cle = next((k for k in self.IMPLEMENTED_SCREENS if k in remote.menus_autorises), None)
        if premiere_cle:
            self.show(premiere_cle)
        else:
            self._show_accueil()

    def _build_menu(self):
        """Barre de menu — mêmes libellés et regroupements que
        l'application de bureau (core.MENU_STRUCTURE), mais un sous-menu
        n'apparaît que s'il est À LA FOIS autorisé pour ce niveau d'accès
        (remote.menus_autorises, transmis par le serveur) ET disponible
        côté client. Un menu de premier niveau sans aucun sous-menu
        correspondant est masqué entièrement — même logique que
        main.py:add_top_menu()."""
        menubar = tk.Menu(self)
        bold = ("Segoe UI", 9, "bold")

        for titre, items in core.MENU_STRUCTURE:
            items_visibles = [(label, key) for label, key in items if key in self.remote.menus_autorises]
            if not items_visibles:
                continue
            m = tk.Menu(menubar, tearoff=0)
            for label, key in items_visibles:
                suffix = "" if key in self.IMPLEMENTED_SCREENS else "  (bientôt disponible)"
                m.add_command(label=label + suffix, command=lambda k=key: self.show(k))
            menubar.add_cascade(label=titre, menu=m)
            menubar.entryconfig(menubar.index("end"), font=bold)

        self.config(menu=menubar)

    def show(self, key):
        if key not in self.IMPLEMENTED_SCREENS:
            messagebox.showinfo(
                "Bientôt disponible",
                f"Cet écran n'est pas encore disponible sur le client réseau — utilisez l'application de "
                f"bureau en attendant. Il suivra le même principe que l'écran Saisie une fois construit.",
                parent=self,
            )
            return
        if key not in self.pages:
            self.pages[key] = self.IMPLEMENTED_SCREENS[key](self.content, self.remote)
            self.pages[key].grid(row=0, column=0, sticky="nsew")
        for page_key, page in self.pages.items():
            if page_key == key:
                page.tkraise()

    def _show_accueil(self):
        frame = ttk.Frame(self.content)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Aucun écran encore disponible pour votre niveau d'accès sur le client réseau.",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=16)
        frame.tkraise()

    def _report_callback_exception(self, exc_type, exc_value, exc_traceback):
        """Gestionnaire d'erreurs global — SANS lui, une exception survenant
        dans un écran (ex. Immobilisations avec des données inhabituelles)
        serait silencieusement avalée par Tkinter (surtout en mode
        --windowed, sans console visible) : l'écran resterait vide, SANS
        AUCUN message, ce qui rend le diagnostic impossible pour
        l'utilisateur. Avec ce gestionnaire, toute erreur devient visible."""
        import traceback
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror(
            "Erreur inattendue",
            f"Une erreur est survenue dans cet écran :\n\n{exc_type.__name__} : {exc_value}\n\n"
            f"Détail technique (à transmettre pour diagnostic) :\n{detail[-1500:]}",
        )

    def _on_close(self):
        self.remote.logout()
        self.destroy()


class RemoteSaisieTab(ttk.Frame):
    """Saisie comptable multi-lignes via le réseau — équivalent distant de
    SaisieTab (main.py), utilisant client_core au lieu de core directement."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.lignes = []  # [{"compte":..., "libelle":..., "debit":..., "credit":...}, ...]

        header = ttk.LabelFrame(self, text="En-tête de l'écriture")
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Date (JJ/MM/AAAA) :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(header, textvariable=self.date_var, width=12).grid(row=0, column=1, padx=4)
        ttk.Label(header, text="Pièce :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.piece_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.piece_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Label(header, text="Journal :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.journal_var = tk.StringVar(value="OD")
        ttk.Combobox(header, textvariable=self.journal_var, width=6, values=("OD", "VE", "AC", "BQ", "CA"),
                     state="readonly").grid(row=0, column=5, padx=4)
        ttk.Label(header, text="Tiers (optionnel) :").grid(row=0, column=6, sticky="w", padx=(12, 4))
        self.tiers_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.tiers_var, width=20).grid(row=0, column=7, padx=4)

        ligne_frame = ttk.LabelFrame(self, text="Ajouter une ligne (compte au débit OU au crédit, pas les deux)")
        ligne_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(ligne_frame, text="Compte :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.compte_var = tk.StringVar()
        self.compte_combo = ttk.Combobox(ligne_frame, textvariable=self.compte_var, width=26)
        self.compte_combo.grid(row=0, column=1, padx=4)
        self.compte_combo.bind("<KeyRelease>", self._on_compte_keyrelease)
        ttk.Label(ligne_frame, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.libelle_var, width=28).grid(row=0, column=3, padx=4)
        ttk.Label(ligne_frame, text="Débit :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.debit_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.debit_var, width=12).grid(row=0, column=5, padx=4)
        ttk.Label(ligne_frame, text="Crédit :").grid(row=0, column=6, sticky="w", padx=(12, 4))
        self.credit_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.credit_var, width=12).grid(row=0, column=7, padx=4)
        ttk.Button(ligne_frame, text="Ajouter la ligne", command=self.ajouter_ligne).grid(row=0, column=8, padx=12)

        cols = ("compte", "libelle", "debit", "credit")
        self.tree_lignes = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, h, w in zip(cols, ["Compte", "Libellé", "Débit", "Crédit"], [110, 340, 120, 120]):
            self.tree_lignes.heading(c, text=h)
            self.tree_lignes.column(c, width=w, anchor="w" if c in ("compte", "libelle") else "e")
        self.tree_lignes.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(self, text="Supprimer la ligne sélectionnée", command=self.supprimer_ligne).pack(
            anchor="w", padx=8, pady=(0, 4))

        self.equilibre_var = tk.StringVar(value="Débit : 0   —   Crédit : 0")
        ttk.Label(self, textvariable=self.equilibre_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        ttk.Button(self, text="Enregistrer l'écriture (via le serveur)", command=self.enregistrer).pack(
            anchor="w", padx=8, pady=8)

        ttk.Separator(self).pack(fill="x", padx=8, pady=4)
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        ttk.Label(bottom, text="Dernières écritures (exercice courant)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w")
        ttk.Button(bottom, text="Actualiser", command=self.refresh_entries).pack(anchor="w", pady=(2, 4))
        cols2 = ("date", "piece", "journal", "compte", "libelle", "debit", "credit")
        self.tree_entries = ttk.Treeview(bottom, columns=cols2, show="headings", height=14)
        for c, h, w in zip(cols2, ["Date", "Pièce", "Journal", "Compte", "Libellé", "Débit", "Crédit"],
                           [85, 90, 60, 90, 300, 110, 110]):
            self.tree_entries.heading(c, text=h)
            self.tree_entries.column(c, width=w, anchor="w" if c not in ("debit", "credit") else "e")
        self.tree_entries.pack(fill="both", expand=True, pady=(0, 4))

        self.refresh_entries()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_compte_keyrelease(self, event=None):
        query = self.compte_var.get().strip()
        items = self._appeler("search_accounts", query, limit=30)
        if items is not APPEL_ECHEC:
            self.compte_combo["values"] = [f"{a['code']} — {a['label']}" for a in items]

    def _extract_code(self, raw):
        raw = (raw or "").strip()
        return raw.split(" — ", 1)[0].strip() if " — " in raw else raw

    def ajouter_ligne(self):
        compte = self._extract_code(self.compte_var.get())
        libelle = self.libelle_var.get().strip()
        if not compte or not libelle:
            messagebox.showwarning("Champ manquant", "Compte et libellé sont obligatoires.", parent=self)
            return
        try:
            debit = float(self.debit_var.get() or 0)
            credit = float(self.credit_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Débit et Crédit doivent être des nombres.", parent=self)
            return
        if debit and credit:
            messagebox.showwarning("Erreur", "Une ligne est soit au débit, soit au crédit — pas les deux.",
                                    parent=self)
            return
        if not debit and not credit:
            messagebox.showwarning("Erreur", "Renseignez un montant au débit ou au crédit.", parent=self)
            return
        self.lignes.append({"compte": compte, "libelle": libelle, "debit": debit, "credit": credit})
        self.compte_var.set(""); self.libelle_var.set(""); self.debit_var.set(""); self.credit_var.set("")
        self._refresh_lignes()

    def supprimer_ligne(self):
        sel = self.tree_lignes.selection()
        if not sel:
            return
        idx = self.tree_lignes.index(sel[0])
        del self.lignes[idx]
        self._refresh_lignes()

    def _refresh_lignes(self):
        for row in self.tree_lignes.get_children():
            self.tree_lignes.delete(row)
        total_debit = total_credit = 0.0
        for l in self.lignes:
            self.tree_lignes.insert("", "end", values=(
                l["compte"], l["libelle"], fmt_cfa(l["debit"]) if l["debit"] else "",
                fmt_cfa(l["credit"]) if l["credit"] else ""))
            total_debit += l["debit"]
            total_credit += l["credit"]
        etat = "✓ Équilibré" if abs(total_debit - total_credit) < 0.01 and self.lignes else ""
        self.equilibre_var.set(f"Débit : {fmt_cfa(total_debit)}   —   Crédit : {fmt_cfa(total_credit)}   {etat}")

    def enregistrer(self):
        if len(self.lignes) < 2:
            messagebox.showwarning("Écriture incomplète", "Ajoutez au moins deux lignes (au moins un débit et un "
                                                            "crédit).", parent=self)
            return
        total_debit = sum(l["debit"] for l in self.lignes)
        total_credit = sum(l["credit"] for l in self.lignes)
        if abs(total_debit - total_credit) >= 0.01:
            messagebox.showwarning("Écriture déséquilibrée",
                                    f"Débit ({fmt_cfa(total_debit)}) ≠ Crédit ({fmt_cfa(total_credit)}).",
                                    parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        piece = self.piece_var.get().strip()
        if not date_str or not piece:
            messagebox.showwarning("Champ manquant", "Date et pièce sont obligatoires.", parent=self)
            return
        journal = self.journal_var.get().strip() or "OD"
        tiers = self.tiers_var.get().strip()

        resultat = self._appeler("add_ecriture_multi_lignes", date_str, piece, journal, self.lignes, tiers=tiers)
        if resultat is APPEL_ECHEC:
            return  # erreur déjà affichée par _appeler (session expirée, réseau, ou règle métier)
        messagebox.showinfo("Enregistré", f"Écriture « {piece} » enregistrée sur le serveur.", parent=self)
        self.lignes = []
        self._refresh_lignes()
        self.piece_var.set("")
        self.refresh_entries()

    def refresh_entries(self):
        exercice = self._appeler("get_current_exercice")
        if exercice is APPEL_ECHEC:
            return
        entries = self._appeler("list_entries", exercice=exercice)
        if entries is APPEL_ECHEC:
            return
        for row in self.tree_entries.get_children():
            self.tree_entries.delete(row)
        for e in entries[-200:][::-1]:  # les 200 plus récentes, plus récentes en premier
            self.tree_entries.insert("", "end", values=(
                core.to_display_date(e["date"]), e["piece"], e["journal"], e["compte"], e["libelle"],
                fmt_cfa(e["debit"]) if e["debit"] else "", fmt_cfa(e["credit"]) if e["credit"] else ""))


class RemotePersonnelTab(ttk.Frame):
    """Liste du personnel (GRH) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None

        ttk.Label(self, text="LISTE DU PERSONNEL", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Employé")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Matricule :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.matricule_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.matricule_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Nom :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.nom_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.nom_var, width=16).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Prénom :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.prenom_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.prenom_var, width=16).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Poste :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.poste_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.poste_var, width=16).grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Label(form, text="Service :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.service_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.service_var, width=16).grid(row=1, column=3, padx=4, pady=(4, 0))
        ttk.Label(form, text="Statut :").grid(row=1, column=4, sticky="w", padx=(12, 4), pady=(4, 0))
        self.statut_var = tk.StringVar(value="actif")
        ttk.Combobox(form, textvariable=self.statut_var, width=13, state="readonly",
                     values=["actif", "congé", "suspendu", "parti"]).grid(row=1, column=5, padx=4, pady=(4, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        cols = ("id", "matricule", "nom", "prenom", "poste", "service", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["ID", "Matricule", "Nom", "Prénom", "Poste", "Service", "Statut"],
                           [40, 100, 130, 130, 150, 130, 90]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_id = v[0]
        self.matricule_var.set(v[1]); self.nom_var.set(v[2]); self.prenom_var.set(v[3])
        self.poste_var.set(v[4]); self.service_var.set(v[5]); self.statut_var.set(v[6])

    def clear_form(self):
        self.selected_id = None
        for var in (self.matricule_var, self.nom_var, self.prenom_var, self.poste_var, self.service_var):
            var.set("")
        self.statut_var.set("actif")

    def add(self):
        if not self.nom_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le nom est obligatoire.", parent=self)
            return
        r = self._appeler("add_personnel", self.nom_var.get(), matricule=self.matricule_var.get(),
                           prenom=self.prenom_var.get(), poste=self.poste_var.get(),
                           service=self.service_var.get(), statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé.", parent=self)
            return
        r = self._appeler("update_personnel", self.selected_id, matricule=self.matricule_var.get().strip(),
                           nom=self.nom_var.get().strip(), prenom=self.prenom_var.get().strip(),
                           poste=self.poste_var.get().strip(), service=self.service_var.get().strip(),
                           statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé.", parent=self)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cet employé ?", parent=self):
            r = self._appeler("delete_personnel", self.selected_id)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        personnel = self._appeler("list_personnel")
        if personnel is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in personnel:
            self.tree.insert("", "end", values=(
                p["id"], p["matricule"] or "", p["nom"], p["prenom"] or "", p["poste"] or "",
                p["service"] or "", p["statut"]))


class RemoteTimeSheetTab(ttk.Frame):
    """Time sheet (GRH) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote

        ttk.Label(self, text="TIME SHEET", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Nouveau pointage")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Employé :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.personnel_var = tk.StringVar()
        self.personnel_combo = ttk.Combobox(form, textvariable=self.personnel_var, width=26, state="readonly")
        self.personnel_combo.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Date (JJ/MM/AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(form, textvariable=self.date_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Heures :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.heures_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.heures_var, width=8).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Activité :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.activite_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.activite_var, width=40).grid(
            row=1, column=1, columnspan=3, padx=4, pady=(4, 0), sticky="we")
        ttk.Button(form, text="Ajouter le pointage", command=self.add).grid(row=1, column=5, padx=4, pady=(4, 0))

        cols = ("id", "employe", "date", "heures", "activite")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["ID", "Employé", "Date", "Heures", "Activité"], [40, 180, 100, 80, 350]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        ttk.Button(self, text="Supprimer la ligne sélectionnée", command=self.delete_sel).pack(
            anchor="w", padx=16, pady=(0, 12))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _refresh_personnel_values(self):
        personnel = self._appeler("list_personnel", actifs_only=True)
        if personnel is APPEL_ECHEC:
            return
        self.personnel_list = personnel
        self.personnel_combo["values"] = [f"{p['id']} — {p['prenom'] or ''} {p['nom']}".strip() for p in personnel]

    def add(self):
        raw = self.personnel_var.get()
        if not raw:
            messagebox.showwarning("Champ manquant", "Choisissez un employé.", parent=self)
            return
        personnel_id = int(raw.split(" — ", 1)[0])
        date_str = core.to_iso_date(self.date_var.get().strip())
        if not date_str:
            messagebox.showwarning("Champ manquant", "La date est obligatoire.", parent=self)
            return
        try:
            heures = float(self.heures_var.get())
        except ValueError:
            messagebox.showerror("Erreur", "Les heures doivent être un nombre.", parent=self)
            return
        r = self._appeler("add_time_sheet", personnel_id, date_str, heures, activite=self.activite_var.get())
        if r is APPEL_ECHEC:
            return
        self.heures_var.set(""); self.activite_var.set("")
        self.refresh()

    def delete_sel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne.", parent=self)
            return
        ts_id = self.tree.item(sel[0], "values")[0]
        r = self._appeler("delete_time_sheet", ts_id)
        if r is APPEL_ECHEC:
            return
        self.refresh()

    def refresh(self):
        self._refresh_personnel_values()
        entries = self._appeler("list_time_sheet")
        if entries is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for t in entries:
            self.tree.insert("", "end", values=(
                t["id"], t["employe"], core.to_display_date(t["date_pointage"]), f"{t['heures']:g}",
                t["activite"] or ""))


class RemoteKpiTab(ttk.Frame):
    """KPI (GRH) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None

        ttk.Label(self, text="KPI — INDICATEURS DE PERFORMANCE", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Indicateur")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Indicateur :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.indicateur_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.indicateur_var, width=28).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Service :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.service_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.service_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Période :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.periode_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.periode_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Valeur cible :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.cible_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.cible_var, width=10).grid(row=1, column=1, padx=4, pady=(4, 0), sticky="w")
        ttk.Label(form, text="Valeur réalisée :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.realisee_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.realisee_var, width=10).grid(row=1, column=3, padx=4, pady=(4, 0), sticky="w")
        ttk.Label(form, text="Statut :").grid(row=1, column=4, sticky="w", padx=(12, 4), pady=(4, 0))
        self.statut_var = tk.StringVar(value="en_cours")
        ttk.Combobox(form, textvariable=self.statut_var, width=13, state="readonly",
                     values=["en_cours", "atteint", "non_atteint"]).grid(row=1, column=5, padx=4, pady=(4, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        cols = ("id", "indicateur", "service", "periode", "cible", "realisee", "taux", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        headers = ["ID", "Indicateur", "Service", "Période", "Cible", "Réalisée", "Taux %", "Statut"]
        widths = [40, 220, 100, 90, 80, 80, 70, 100]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_id = v[0]
        self.indicateur_var.set(v[1]); self.service_var.set(v[2]); self.periode_var.set(v[3])
        self.cible_var.set(v[4]); self.realisee_var.set(v[5]); self.statut_var.set(v[7])

    def clear_form(self):
        self.selected_id = None
        for var in (self.indicateur_var, self.service_var, self.periode_var, self.cible_var, self.realisee_var):
            var.set("")
        self.statut_var.set("en_cours")

    def add(self):
        if not self.indicateur_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le nom de l'indicateur est obligatoire.", parent=self)
            return
        try:
            cible = float(self.cible_var.get() or 0)
            realisee = float(self.realisee_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Cible et Réalisée doivent être des nombres.", parent=self)
            return
        r = self._appeler("add_kpi", self.indicateur_var.get(), service=self.service_var.get(),
                           periode=self.periode_var.get(), valeur_cible=cible, valeur_realisee=realisee,
                           statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un indicateur.", parent=self)
            return
        try:
            cible = float(self.cible_var.get() or 0)
            realisee = float(self.realisee_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Cible et Réalisée doivent être des nombres.", parent=self)
            return
        r = self._appeler("update_kpi", self.selected_id, indicateur=self.indicateur_var.get().strip(),
                           service=self.service_var.get().strip(), periode=self.periode_var.get().strip(),
                           valeur_cible=cible, valeur_realisee=realisee, statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un indicateur.", parent=self)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cet indicateur ?", parent=self):
            r = self._appeler("delete_kpi", self.selected_id)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        kpis = self._appeler("list_kpi")
        if kpis is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for k in kpis:
            taux = f"{k['taux_realisation']:.0f}" if k["taux_realisation"] is not None else ""
            self.tree.insert("", "end", values=(
                k["id"], k["indicateur"], k["service"] or "", k["periode"] or "",
                f"{k['valeur_cible']:g}", f"{k['valeur_realisee']:g}", taux, k["statut"]))


class RemoteTableauBordGrhTab(ttk.Frame):
    """Tableau de bord GRH (synthèse en lecture seule) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="TABLEAU DE BORD GRH", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16)
        self.cards_frame = ttk.Frame(self)
        self.cards_frame.pack(fill="x", padx=16, pady=16)
        self.hs_frame = ttk.LabelFrame(self, text="Incidents HS ouverts, par gravité")
        self.hs_frame.pack(fill="x", padx=16, pady=8)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _card(self, parent, titre, valeur, col, couleur="#1F4E78"):
        f = ttk.Frame(parent, relief="solid", borderwidth=1)
        f.grid(row=0, column=col, padx=8, sticky="nsew")
        parent.columnconfigure(col, weight=1)
        tk.Label(f, text=titre, font=("Segoe UI", 9), bg="white", fg="#595959").pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(f, text=str(valeur), font=("Segoe UI", 20, "bold"), bg="white", fg=couleur).pack(
            fill="x", padx=12, pady=(0, 10))

    def refresh(self):
        d = self._appeler("compute_tableau_bord_grh")
        if d is APPEL_ECHEC:
            return
        for w in self.cards_frame.winfo_children():
            w.destroy()
        for w in self.hs_frame.winfo_children():
            w.destroy()
        self._card(self.cards_frame, "Personnel actif", f"{d['nb_personnel_actif']} / {d['nb_personnel_total']}", 0)
        self._card(self.cards_frame, "Heures pointées (30j)", f"{d['total_heures_30j']:g} h", 1)
        self._card(self.cards_frame, "KPI en cours", d["nb_kpi_en_cours"], 2)
        self._card(self.cards_frame, "KPI atteints", d["nb_kpi_atteints"], 3, couleur="#1F7A1F")
        self._card(self.cards_frame, "KPI non atteints", d["nb_kpi_non_atteints"], 4, couleur="#B00020")
        self._card(self.cards_frame, "Incidents HS ouverts", d["nb_hs_ouverts"], 5,
                   couleur="#B00020" if d["nb_hs_ouverts"] else "#1F7A1F")
        if not d["hs_par_gravite"]:
            ttk.Label(self.hs_frame, text="Aucun incident ouvert.", foreground="#1F7A1F").pack(
                anchor="w", padx=12, pady=8)
        else:
            for gravite, nb in d["hs_par_gravite"].items():
                ttk.Label(self.hs_frame, text=f"• {gravite} : {nb}").pack(anchor="w", padx=12, pady=2)


class RemoteHsTab(ttk.Frame):
    """HS — Hygiène Santé (GRH) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None

        ttk.Label(self, text="HS — HYGIÈNE SANTÉ", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Événement")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Date (JJ/MM/AAAA) :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(form, textvariable=self.date_var, width=12).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Type :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.type_var = tk.StringVar(value="incident")
        ttk.Combobox(form, textvariable=self.type_var, width=17, state="readonly",
                     values=["incident", "visite_medicale", "formation_securite", "distribution_epi"]).grid(
            row=0, column=3, padx=4)
        ttk.Label(form, text="Gravité :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.gravite_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.gravite_var, width=13, state="readonly",
                     values=["", "Mineure", "Modérée", "Grave"]).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Statut :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.statut_var = tk.StringVar(value="ouvert")
        ttk.Combobox(form, textvariable=self.statut_var, width=13, state="readonly",
                     values=["ouvert", "clos"]).grid(row=1, column=1, padx=4, pady=(4, 0), sticky="w")
        ttk.Label(form, text="Description :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.description_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.description_var, width=50).grid(
            row=1, column=3, columnspan=3, padx=4, pady=(4, 0), sticky="we")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        cols = ("id", "date", "type", "gravite", "statut", "description")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        headers = ["ID", "Date", "Type", "Gravité", "Statut", "Description"]
        widths = [40, 90, 140, 90, 80, 380]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_id = v[0]
        self.date_var.set(v[1]); self.type_var.set(v[2])
        self.gravite_var.set(v[3]); self.statut_var.set(v[4]); self.description_var.set(v[5])

    def clear_form(self):
        self.selected_id = None
        self.date_var.set(date.today().strftime("%d/%m/%Y"))
        self.type_var.set("incident"); self.gravite_var.set(""); self.statut_var.set("ouvert")
        self.description_var.set("")

    def add(self):
        date_str = core.to_iso_date(self.date_var.get().strip())
        if not date_str:
            messagebox.showwarning("Champ manquant", "La date est obligatoire.", parent=self)
            return
        r = self._appeler("add_hs", date_str, type_evenement=self.type_var.get(),
                           description=self.description_var.get(), gravite=self.gravite_var.get(),
                           statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un événement.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        r = self._appeler("update_hs", self.selected_id, date_evenement=date_str, type_evenement=self.type_var.get(),
                           description=self.description_var.get().strip(), gravite=self.gravite_var.get(),
                           statut=self.statut_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un événement.", parent=self)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cet événement ?", parent=self):
            r = self._appeler("delete_hs", self.selected_id)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        events = self._appeler("list_hs")
        if events is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for h in events:
            self.tree.insert("", "end", values=(
                h["id"], core.to_display_date(h["date_evenement"]), h["type_evenement"], h["gravite"] or "",
                h["statut"], h["description"] or ""))


class RemoteFournisseursTab(ttk.Frame):
    """Fournisseurs (ENGAGEMENTS-PROJETS) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_code = None

        ttk.Label(self, text="FOURNISSEURS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Fournisseur")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Code :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(form, textvariable=self.code_var, width=14)
        self.code_entry.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Raison sociale :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.raison_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.raison_var, width=30).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Contact :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.contact_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.contact_var, width=20).grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Label(form, text="Téléphone :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.telephone_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.telephone_var, width=18).grid(row=1, column=3, padx=4, pady=(4, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        recherche = ttk.Frame(self)
        recherche.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Label(recherche, text="Rechercher :").pack(side="left")
        self.recherche_var = tk.StringVar()
        recherche_entry = ttk.Entry(recherche, textvariable=self.recherche_var, width=30)
        recherche_entry.pack(side="left", padx=4)
        recherche_entry.bind("<KeyRelease>", lambda e: self.refresh())

        cols = ("code", "raison_sociale", "contact", "telephone")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["Code", "Raison sociale", "Contact", "Téléphone"], [100, 280, 180, 140]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_code = v[0]
        self.code_var.set(v[0]); self.raison_var.set(v[1])
        self.contact_var.set(v[2]); self.telephone_var.set(v[3])
        self.code_entry.configure(state="disabled")

    def clear_form(self):
        self.selected_code = None
        self.code_var.set(""); self.raison_var.set(""); self.contact_var.set(""); self.telephone_var.set("")
        self.code_entry.configure(state="normal")

    def add(self):
        if not self.code_var.get().strip() or not self.raison_var.get().strip():
            messagebox.showwarning("Champ manquant", "Code et raison sociale sont obligatoires.", parent=self)
            return
        r = self._appeler("add_fournisseur", self.code_var.get(), self.raison_var.get(),
                           contact=self.contact_var.get(), telephone=self.telephone_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un fournisseur.", parent=self)
            return
        r = self._appeler("add_fournisseur", self.selected_code, self.raison_var.get(),
                           contact=self.contact_var.get(), telephone=self.telephone_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un fournisseur.", parent=self)
            return
        if messagebox.askyesno("Confirmer", f"Supprimer le fournisseur « {self.selected_code} » ?", parent=self):
            r = self._appeler("delete_fournisseur", self.selected_code)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        fournisseurs = self._appeler("list_fournisseurs", self.recherche_var.get().strip() or None)
        if fournisseurs is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for f in fournisseurs:
            self.tree.insert("", "end", values=(
                f["code"], f["raison_sociale"], f["contact"] or "", f["telephone"] or ""))


class RemoteReglementsTab(ttk.Frame):
    """Règlements fournisseurs (ENGAGEMENTS-PROJETS) via le réseau — un
    règlement validé comptabilise directement l'achat (débit du compte de
    charge choisi par ligne, crédit fournisseur), exactement comme sur
    l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.reglement_id_selectionne = None
        self.lignes = []  # [{"compte_charge":..., "libelle":..., "quantite":..., "prix_unitaire":...}, ...]

        ttk.Label(self, text="RÈGLEMENTS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        header = ttk.LabelFrame(self, text="Nouveau règlement")
        header.pack(fill="x", padx=16, pady=4)
        ttk.Label(header, text="Numéro :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.numero_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.numero_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(header, text="Date (JJ/MM/AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(header, textvariable=self.date_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(header, text="Fournisseur (code) :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.fournisseur_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.fournisseur_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Button(header, text="Créer le règlement", command=self.creer).grid(row=0, column=6, padx=12)

        ligne_frame = ttk.LabelFrame(self, text="Lignes (une fois le règlement créé, sélectionné dans la liste)")
        ligne_frame.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(ligne_frame, text="Compte de charge :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.compte_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.compte_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(ligne_frame, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.libelle_var, width=26).grid(row=0, column=3, padx=4)
        ttk.Label(ligne_frame, text="Quantité :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.quantite_var = tk.StringVar(value="1")
        ttk.Entry(ligne_frame, textvariable=self.quantite_var, width=8).grid(row=0, column=5, padx=4)
        ttk.Label(ligne_frame, text="Prix unitaire :").grid(row=0, column=6, sticky="w", padx=(12, 4))
        self.prix_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.prix_var, width=12).grid(row=0, column=7, padx=4)
        ttk.Button(ligne_frame, text="Ajouter la ligne", command=self.ajouter_ligne).grid(row=0, column=8, padx=12)

        self.tree_lignes = ttk.Treeview(self, columns=("compte", "libelle", "qte", "prix"), show="headings",
                                         height=6)
        for c, h, w in zip(("compte", "libelle", "qte", "prix"), ["Compte", "Libellé", "Qté", "Prix unit."],
                           [100, 300, 60, 110]):
            self.tree_lignes.heading(c, text=h)
            self.tree_lignes.column(c, width=w, anchor="w")
        self.tree_lignes.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(self, text="Valider le règlement (comptabilise l'achat sur le serveur)",
                   command=self.valider).pack(anchor="w", padx=16, pady=8)

        ttk.Separator(self).pack(fill="x", padx=16, pady=4)
        ttk.Label(self, text="Règlements existants", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(2, 4))
        cols = ("id", "numero", "date", "fournisseur", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c, h, w in zip(cols, ["ID", "Numéro", "Date", "Fournisseur", "Statut"], [40, 100, 90, 260, 100]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_reglement)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def creer(self):
        if not self.numero_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le numéro est obligatoire.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        rid = self._appeler("create_reglement", self.numero_var.get(), date_str,
                             fournisseur_code=self.fournisseur_var.get().strip())
        if rid is APPEL_ECHEC:
            return
        self.reglement_id_selectionne = rid
        messagebox.showinfo("Créé", f"Règlement « {self.numero_var.get()} » créé (brouillon) — ajoutez des "
                                     f"lignes puis validez.", parent=self)
        self.numero_var.set("")
        self.refresh()

    def ajouter_ligne(self):
        if not self.reglement_id_selectionne:
            messagebox.showinfo("Info", "Créez ou sélectionnez d'abord un règlement dans la liste.", parent=self)
            return
        compte = self.compte_var.get().strip()
        libelle = self.libelle_var.get().strip()
        if not compte or not libelle:
            messagebox.showwarning("Champ manquant", "Compte de charge et libellé sont obligatoires.", parent=self)
            return
        try:
            qte = float(self.quantite_var.get() or 0)
            prix = float(self.prix_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Quantité et Prix unitaire doivent être des nombres.", parent=self)
            return
        r = self._appeler("add_ligne_reglement", self.reglement_id_selectionne, compte, libelle, qte,
                           prix_unitaire=prix)
        if r is APPEL_ECHEC:
            return
        self.compte_var.set(""); self.libelle_var.set(""); self.quantite_var.set("1"); self.prix_var.set("")
        self._refresh_lignes()

    def valider(self):
        if not self.reglement_id_selectionne:
            messagebox.showinfo("Info", "Sélectionnez d'abord un règlement dans la liste.", parent=self)
            return
        if not messagebox.askyesno("Valider ce règlement",
                                    "Le règlement va être comptabilisé sur le serveur (débit des comptes de "
                                    "charge, crédit fournisseur). Continuer ?", parent=self):
            return
        r = self._appeler("valider_reglement", self.reglement_id_selectionne)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Validé", "Règlement comptabilisé sur le serveur.", parent=self)
        self.refresh()

    def _on_select_reglement(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.reglement_id_selectionne = int(v[0])
        self._refresh_lignes()

    def _refresh_lignes(self):
        for row in self.tree_lignes.get_children():
            self.tree_lignes.delete(row)
        if not self.reglement_id_selectionne:
            return
        lignes = self._appeler("list_lignes_reglement", self.reglement_id_selectionne)
        if lignes is APPEL_ECHEC:
            return
        for l in lignes:
            self.tree_lignes.insert("", "end", values=(
                l["compte_charge"] or "⚠ à choisir", l["libelle"], f"{l['quantite']:g}",
                fmt_cfa(l["prix_unitaire"])))

    def refresh(self):
        reglements = self._appeler("list_reglements")
        if reglements is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in reglements:
            self.tree.insert("", "end", values=(
                r["id"], r["numero"], core.to_display_date(r["date_reglement"]), r["raison_sociale"], r["statut"]))


class RemoteEtatFormuleTab(ttk.Frame):
    """Écran générique en lecture seule pour les états basés sur
    compute_etat_formule_generique() côté serveur (Compte de résultat,
    TFT, Situation financière) — même principe que EtatFormuleTab dans
    l'application de bureau, réutilisé pour les 3 rapports qui partagent
    la même structure « Rubrique | N (| N-1 | %) »."""

    def __init__(self, parent, remote: RemoteConnection, titre, fonction):
        super().__init__(parent)
        self.remote = remote
        self.titre = titre
        self.fonction = fonction

        ttk.Label(self, text=titre, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 8))

        self.tree = ttk.Treeview(self, columns=("libelle", "n", "n1", "pct"), show="headings", height=32)
        self.tree.heading("libelle", text="Rubrique")
        self.tree.column("libelle", width=460, anchor="w", stretch=True)
        for c in ("n", "n1", "pct"):
            self.tree.column(c, width=150, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        d = self._appeler(self.fonction)
        if d is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        headers = {"N": "Exercice N", "N-1": "Exercice N-1", "%": "%"}
        cols = ("n", "n1", "pct")
        for col_key, label in zip(cols, d["colonnes"] + [""] * 3):
            self.tree.heading(col_key, text=headers.get(label, label) if label else "")
        for l in d["lignes"]:
            valeurs = [l.get(c, None) for c in d["colonnes"]]
            while len(valeurs) < 3:
                valeurs.append(None)
            self.tree.insert("", "end", values=(l["libelle"], fmt_cfa(valeurs[0]), fmt_cfa(valeurs[1]),
                                                 fmt_cfa(valeurs[2])))


class RemoteBilanTab(ttk.Frame):
    """Bilan SYSCOHADA en lecture seule via le réseau — même moteur
    (compute_bilan_detaille) que l'application de bureau, présentation
    simplifiée (colonnes Net et Net N-1 uniquement, sans le détail
    Brut/Amortissements, pour une vue rapide)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="BILAN SYSCOHADA", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        btn_bar = ttk.Frame(self)
        btn_bar.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(btn_bar, text="Actualiser", command=self.refresh).pack(side="left")
        self.ecart_var = tk.StringVar()
        self.ecart_label = ttk.Label(btn_bar, textvariable=self.ecart_var, font=("Segoe UI", 10, "bold"))
        self.ecart_label.pack(side="left", padx=16)

        columns_frame = ttk.Frame(self)
        columns_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=1)
        self.tree_actif = ttk.Treeview(columns_frame, columns=("libelle", "net", "net_n1"), show="headings", height=30)
        for c, h, w in zip(("libelle", "net", "net_n1"), ["ACTIF", "Net", "Net N-1"], [260, 130, 130]):
            self.tree_actif.heading(c, text=h)
            self.tree_actif.column(c, width=w, anchor="w" if c == "libelle" else "e")
        self.tree_actif.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.tree_passif = ttk.Treeview(columns_frame, columns=("libelle", "montant", "montant_n1"),
                                         show="headings", height=30)
        for c, h, w in zip(("libelle", "montant", "montant_n1"), ["PASSIF", "Montant", "Montant N-1"],
                           [280, 140, 140]):
            self.tree_passif.heading(c, text=h)
            self.tree_passif.column(c, width=w, anchor="w" if c == "libelle" else "e")
        self.tree_passif.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _add_actif(self, titre, lignes, total_label, total_val, total_val_n1, montant_field="net"):
        self.tree_actif.insert("", "end", values=(titre, "", ""))
        for l in lignes:
            montant = l.get(montant_field, 0)
            montant_n1 = l.get(f"{montant_field}_n1", 0)
            if montant or montant_n1:
                self.tree_actif.insert("", "end", values=(f"  {l['label']}", fmt_cfa(montant), fmt_cfa(montant_n1)))
        self.tree_actif.insert("", "end", values=(f"  {total_label}", fmt_cfa(total_val), fmt_cfa(total_val_n1)))

    def _add_passif(self, titre, lignes, total_label, total_val, total_val_n1):
        self.tree_passif.insert("", "end", values=(titre, "", ""))
        for l in lignes:
            montant = l.get("sous_total", 0)
            montant_n1 = l.get("sous_total_n1", 0)
            if montant or montant_n1:
                self.tree_passif.insert("", "end", values=(f"  {l['label']}", fmt_cfa(montant), fmt_cfa(montant_n1)))
        self.tree_passif.insert("", "end", values=(f"  {total_label}", fmt_cfa(total_val), fmt_cfa(total_val_n1)))

    def refresh(self):
        d = self._appeler("compute_bilan_detaille")
        if d is APPEL_ECHEC:
            return
        for tree in (self.tree_actif, self.tree_passif):
            for row in tree.get_children():
                tree.delete(row)
        a, p = d["actif"], d["passif"]
        self._add_actif("IMMOBILISATIONS", a["immobilisations"], "Total immobilisations nettes",
                         a["total_immo_net"], a["total_immo_net_n1"])
        self._add_actif("STOCKS", a["stocks"], "Total stocks", a["total_stocks"], a["total_stocks_n1"],
                         montant_field="sous_total")
        self._add_actif("CRÉANCES", a["creances"], "Total créances", a["total_creances"], a["total_creances_n1"],
                         montant_field="sous_total")
        self._add_actif("TRÉSORERIE ACTIF", a["tresorerie"], "Total trésorerie actif", a["total_tresorerie"],
                         a["total_tresorerie_n1"], montant_field="sous_total")
        self.tree_actif.insert("", "end", values=("TOTAL ACTIF", fmt_cfa(d["total_actif"]), fmt_cfa(d["total_actif_n1"])))
        self._add_passif("CAPITAUX PROPRES", p["capitaux_propres"], "Total capitaux propres",
                          p["total_capitaux_propres"], p["total_capitaux_propres_n1"])
        self._add_passif("DETTES CIRCULANTES", p["dettes"], "Total dettes circulantes", p["total_dettes"],
                          p["total_dettes_n1"])
        self._add_passif("TRÉSORERIE PASSIF", p["tresorerie"], "Total trésorerie passif", p["total_tresorerie"],
                          p["total_tresorerie_n1"])
        self.tree_passif.insert("", "end", values=("TOTAL PASSIF", fmt_cfa(d["total_passif"]), fmt_cfa(d["total_passif_n1"])))

        ecart = d["ecart"]
        if abs(ecart) < 1:
            self.ecart_var.set(f"✓ Actif = Passif ({fmt_cfa(d['total_actif'])})")
            self.ecart_label.configure(foreground="#1F7A1F")
        else:
            self.ecart_var.set(f"⚠ Écart Actif - Passif : {fmt_cfa(ecart)}")
            self.ecart_label.configure(foreground="#B00020")


class RemoteBalanceTab(ttk.Frame):
    """Balance générale en lecture seule via le réseau — 6 colonnes
    (Ouverture/Mouvement/Clôture Débit/Crédit), même moteur que
    l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="BALANCE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("compte", "libelle", "ouv_debit", "ouv_credit", "mvt_debit", "mvt_credit", "sold_debit", "sold_credit")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=30)
        headers = ["N° Compte", "Libellé", "Ouv. Débit", "Ouv. Crédit", "Mvt Débit", "Mvt Crédit",
                   "Clôt. Débit", "Clôt. Crédit"]
        widths = [90, 220, 100, 100, 100, 100, 100, 100]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("compte", "libelle") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        d = self._appeler("compute_balance_detaillee")
        if d is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in d["classes"]:
            for l in c["lignes"]:
                self.tree.insert("", "end", values=(
                    l["code"], l["label"], fmt_cfa(l["ouverture_debit"]), fmt_cfa(l["ouverture_credit"]),
                    fmt_cfa(l["cumul_debit"]), fmt_cfa(l["cumul_credit"]), fmt_cfa(l["solde_debit"]),
                    fmt_cfa(l["solde_credit"])))
            st = c["sous_total"]
            self.tree.insert("", "end", values=(
                "", f"TOTAL CLASSE {c['classe']}", fmt_cfa(st["ouverture_debit"]), fmt_cfa(st["ouverture_credit"]),
                fmt_cfa(st["cumul_debit"]), fmt_cfa(st["cumul_credit"]), fmt_cfa(st["solde_debit"]),
                fmt_cfa(st["solde_credit"])))
        gt = d["grand_total"]
        self.tree.insert("", "end", values=(
            "", "TOTAL BALANCE", fmt_cfa(gt["ouverture_debit"]), fmt_cfa(gt["ouverture_credit"]),
            fmt_cfa(gt["cumul_debit"]), fmt_cfa(gt["cumul_credit"]), fmt_cfa(gt["solde_debit"]),
            fmt_cfa(gt["solde_credit"])))


class RemoteGrandLivreTab(ttk.Frame):
    """Grand livre en lecture seule via le réseau — détail écriture par
    écriture, groupé par compte puis par classe."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="GRAND LIVRE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("date", "piece", "journal", "libelle", "debit", "credit")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=30)
        for c, h, w in zip(cols, ["Date", "Pièce", "Journal", "Libellé", "Débit", "Crédit"],
                           [85, 90, 60, 400, 110, 110]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c not in ("debit", "credit") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        classes = self._appeler("compute_grand_livre_complet")
        if classes is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in classes:
            for compte in c["comptes"]:
                self.tree.insert("", "end", values=("", "", "", f"{compte['code']} — {compte['label']}", "", ""))
                for l in compte["lignes"]:
                    self.tree.insert("", "end", values=(
                        core.to_display_date(l["date"]), l["piece"] or "", l["journal"] or "", l["libelle"] or "",
                        fmt_cfa(l["debit"]) if l["debit"] else "", fmt_cfa(l["credit"]) if l["credit"] else ""))
                self.tree.insert("", "end", values=(
                    "", "", "", f"TOTAL COMPTE {compte['code']} — Solde {compte['sens']}",
                    fmt_cfa(compte["total_debit"]), fmt_cfa(compte["total_credit"])))


class RemoteClientsTab(ttk.Frame):
    """Clients (COMMERCIAL) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_code = None

        ttk.Label(self, text="CLIENTS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Client")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Code :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(form, textvariable=self.code_var, width=14)
        self.code_entry.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Raison sociale :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.raison_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.raison_var, width=30).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Contact :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.contact_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.contact_var, width=20).grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Label(form, text="Téléphone :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.telephone_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.telephone_var, width=18).grid(row=1, column=3, padx=4, pady=(4, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        cols = ("code", "raison_sociale", "contact", "telephone")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, h, w in zip(cols, ["Code", "Raison sociale", "Contact", "Téléphone"], [100, 280, 180, 140]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_code = v[0]
        self.code_var.set(v[0]); self.raison_var.set(v[1])
        self.contact_var.set(v[2]); self.telephone_var.set(v[3])
        self.code_entry.configure(state="disabled")

    def clear_form(self):
        self.selected_code = None
        self.code_var.set(""); self.raison_var.set(""); self.contact_var.set(""); self.telephone_var.set("")
        self.code_entry.configure(state="normal")

    def add(self):
        if not self.code_var.get().strip() or not self.raison_var.get().strip():
            messagebox.showwarning("Champ manquant", "Code et raison sociale sont obligatoires.", parent=self)
            return
        r = self._appeler("add_client", self.code_var.get(), self.raison_var.get(),
                           contact=self.contact_var.get(), telephone=self.telephone_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un client.", parent=self)
            return
        r = self._appeler("add_client", self.selected_code, self.raison_var.get(),
                           contact=self.contact_var.get(), telephone=self.telephone_var.get())
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un client.", parent=self)
            return
        if messagebox.askyesno("Confirmer", f"Supprimer le client « {self.selected_code} » ?", parent=self):
            r = self._appeler("delete_client", self.selected_code)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        clients = self._appeler("list_clients")
        if clients is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in clients:
            self.tree.insert("", "end", values=(c["code"], c["raison_sociale"], c["contact"] or "",
                                                 c["telephone"] or ""))


class RemoteFacturationTab(ttk.Frame):
    """Facturation clients (COMMERCIAL) via le réseau — une facture
    validée comptabilise directement la vente (débit client, crédit
    compte de vente + TVA), même moteur que l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.facture_id_selectionnee = None

        ttk.Label(self, text="FACTURATION", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        header = ttk.LabelFrame(self, text="Nouvelle facture")
        header.pack(fill="x", padx=16, pady=4)
        ttk.Label(header, text="Numéro :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.numero_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.numero_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(header, text="Date (JJ/MM/AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(header, textvariable=self.date_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(header, text="Client (code) :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.client_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.client_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Button(header, text="Créer la facture", command=self.creer).grid(row=0, column=6, padx=12)

        ligne_frame = ttk.LabelFrame(self, text="Lignes (une fois la facture créée, sélectionnée dans la liste)")
        ligne_frame.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(ligne_frame, text="Compte de vente :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.compte_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.compte_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(ligne_frame, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.libelle_var, width=26).grid(row=0, column=3, padx=4)
        ttk.Label(ligne_frame, text="Quantité :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.quantite_var = tk.StringVar(value="1")
        ttk.Entry(ligne_frame, textvariable=self.quantite_var, width=8).grid(row=0, column=5, padx=4)
        ttk.Label(ligne_frame, text="Prix unitaire :").grid(row=0, column=6, sticky="w", padx=(12, 4))
        self.prix_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.prix_var, width=12).grid(row=0, column=7, padx=4)
        ttk.Button(ligne_frame, text="Ajouter la ligne", command=self.ajouter_ligne).grid(row=0, column=8, padx=12)

        self.tree_lignes = ttk.Treeview(self, columns=("compte", "libelle", "qte", "prix"), show="headings",
                                         height=6)
        for c, h, w in zip(("compte", "libelle", "qte", "prix"), ["Compte", "Libellé", "Qté", "Prix unit."],
                           [100, 300, 60, 110]):
            self.tree_lignes.heading(c, text=h)
            self.tree_lignes.column(c, width=w, anchor="w")
        self.tree_lignes.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(self, text="Valider la facture (comptabilise la vente sur le serveur)",
                   command=self.valider).pack(anchor="w", padx=16, pady=8)

        ttk.Separator(self).pack(fill="x", padx=16, pady=4)
        ttk.Label(self, text="Factures existantes", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(2, 4))
        cols = ("id", "numero", "date", "client", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c, h, w in zip(cols, ["ID", "Numéro", "Date", "Client", "Statut"], [40, 100, 90, 260, 100]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_facture)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def creer(self):
        if not self.numero_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le numéro est obligatoire.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        fid = self._appeler("create_facture_vente", self.numero_var.get(), date_str, self.client_var.get().strip())
        if fid is APPEL_ECHEC:
            return
        self.facture_id_selectionnee = fid
        messagebox.showinfo("Créée", f"Facture « {self.numero_var.get()} » créée (brouillon) — ajoutez des "
                                      f"lignes puis validez.", parent=self)
        self.numero_var.set("")
        self.refresh()

    def ajouter_ligne(self):
        if not self.facture_id_selectionnee:
            messagebox.showinfo("Info", "Créez ou sélectionnez d'abord une facture dans la liste.", parent=self)
            return
        compte = self.compte_var.get().strip()
        libelle = self.libelle_var.get().strip()
        if not compte or not libelle:
            messagebox.showwarning("Champ manquant", "Compte de vente et libellé sont obligatoires.", parent=self)
            return
        try:
            qte = float(self.quantite_var.get() or 0)
            prix = float(self.prix_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Quantité et Prix unitaire doivent être des nombres.", parent=self)
            return
        r = self._appeler("add_ligne_facture_vente", self.facture_id_selectionnee, compte, libelle, qte, prix)
        if r is APPEL_ECHEC:
            return
        self.compte_var.set(""); self.libelle_var.set(""); self.quantite_var.set("1"); self.prix_var.set("")
        self._refresh_lignes()

    def valider(self):
        if not self.facture_id_selectionnee:
            messagebox.showinfo("Info", "Sélectionnez d'abord une facture dans la liste.", parent=self)
            return
        if not messagebox.askyesno("Valider cette facture",
                                    "La facture va être comptabilisée sur le serveur (débit client, crédit "
                                    "vente + TVA). Continuer ?", parent=self):
            return
        r = self._appeler("valider_facture_vente", self.facture_id_selectionnee)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Validée", "Facture comptabilisée sur le serveur.", parent=self)
        self.refresh()

    def _on_select_facture(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.facture_id_selectionnee = int(v[0])
        self._refresh_lignes()

    def _refresh_lignes(self):
        for row in self.tree_lignes.get_children():
            self.tree_lignes.delete(row)
        if not self.facture_id_selectionnee:
            return
        lignes = self._appeler("list_lignes_facture_vente", self.facture_id_selectionnee)
        if lignes is APPEL_ECHEC:
            return
        for l in lignes:
            self.tree_lignes.insert("", "end", values=(
                l["compte_vente"], l["libelle"], f"{l['quantite']:g}", fmt_cfa(l["prix_unitaire"])))

    def refresh(self):
        factures = self._appeler("list_factures_vente")
        if factures is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for f in factures:
            self.tree.insert("", "end", values=(
                f["id"], f["numero"], core.to_display_date(f["date_facture"]), f["raison_sociale"], f["statut"]))


class RemoteStocksTab(ttk.Frame):
    """Stocks en lecture seule via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="STOCKS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("compte", "libelle", "initial", "entrees", "sorties", "final")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for c, h, w in zip(cols, ["Compte", "Libellé", "Stock initial", "Entrées", "Sorties", "Stock final"],
                           [90, 260, 130, 130, 130, 130]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("compte", "libelle") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        stocks = self._appeler("compute_stocks")
        if stocks is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in stocks:
            self.tree.insert("", "end", values=(
                s["code"], s["label"], fmt_cfa(s["stock_initial"]), fmt_cfa(s["entrees"]), fmt_cfa(s["sorties"]),
                fmt_cfa(s["stock_final"])))


class RemoteTresorerieTab(ttk.Frame):
    """Trésorerie en lecture seule via le réseau — banques horizontales
    et engagements à payer."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="TRÉSORERIE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))

        ttk.Label(self, text="Banques (Entrées / Sorties)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=16, pady=(8, 2))
        cols1 = ("compte", "libelle", "debut", "entrees", "sorties", "fin")
        self.tree_banques = ttk.Treeview(self, columns=cols1, show="headings", height=8)
        for c, h, w in zip(cols1, ["Compte", "Libellé", "Solde début", "Entrées", "Sorties", "Solde fin"],
                           [90, 220, 130, 130, 130, 140]):
            self.tree_banques.heading(c, text=h)
            self.tree_banques.column(c, width=w, anchor="w" if c in ("compte", "libelle") else "e")
        self.tree_banques.pack(fill="x", padx=16, pady=(0, 8))

        self.synthese_var = tk.StringVar()
        ttk.Label(self, textvariable=self.synthese_var, font=("Segoe UI", 10, "bold"), wraplength=1200).pack(
            anchor="w", padx=16, pady=(4, 4))
        ttk.Label(self, text="Engagements à payer (règlements validés, non encore payés)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(8, 2))
        cols2 = ("numero", "date", "fournisseur", "montant")
        self.tree_engagements = ttk.Treeview(self, columns=cols2, show="headings", height=10)
        for c, h, w in zip(cols2, ["N° Règlement", "Date", "Fournisseur", "Montant net à payer"],
                           [130, 100, 260, 160]):
            self.tree_engagements.heading(c, text=h)
            self.tree_engagements.column(c, width=w, anchor="w" if c != "montant" else "e")
        self.tree_engagements.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        r1 = self._appeler("compute_tresorerie_banques_horizontal")
        if r1 is APPEL_ECHEC:
            return
        lignes, total = r1
        for row in self.tree_banques.get_children():
            self.tree_banques.delete(row)
        for l in lignes:
            self.tree_banques.insert("", "end", values=(
                l["code"], l["label"], fmt_cfa(l["solde_debut_periode"]), fmt_cfa(l["debit_periode"]),
                fmt_cfa(l["credit_periode"]), fmt_cfa(l["solde_fin_periode"])))
        self.tree_banques.insert("", "end", values=(
            "TOTAL", "", fmt_cfa(total["solde_debut_periode"]), fmt_cfa(total["debit_periode"]),
            fmt_cfa(total["credit_periode"]), fmt_cfa(total["solde_fin_periode"])))

        d = self._appeler("compute_engagements_a_payer")
        if d is APPEL_ECHEC:
            return
        for row in self.tree_engagements.get_children():
            self.tree_engagements.delete(row)
        for e in d["engagements"]:
            self.tree_engagements.insert("", "end", values=(
                e["numero"], core.to_display_date(e["date_reglement"]), e["raison_sociale"],
                fmt_cfa(e["net_a_payer"])))
        etat = "✓ peut faire face" if d["peut_faire_face"] else "⚠ insuffisant"
        self.synthese_var.set(f"Trésorerie disponible : {fmt_cfa(d['treso_disponible'])}   —   Engagements : "
                               f"{fmt_cfa(d['total_engagements'])}   —   {etat}")


class RemoteImmobilisationsTab(ttk.Frame):
    """Immobilisations en lecture seule via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="IMMOBILISATIONS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("compte", "libelle", "categorie", "brut", "amort", "net")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=24)
        for c, h, w in zip(cols, ["Compte", "Libellé", "Catégorie", "Valeur brute", "Amortissement", "Valeur nette"],
                           [90, 220, 200, 130, 130, 130]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("compte", "libelle", "categorie") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        immos = self._appeler("compute_immobilisations_liste")
        if immos is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i in immos:
            self.tree.insert("", "end", values=(
                i["compte"], i["libelle"], i.get("categorie") or "", fmt_cfa(i["valeur_brute"]),
                fmt_cfa(i["amortissement"]), fmt_cfa(i["valeur_nette"])))


class RemoteExpressionBesoinTab(ttk.Frame):
    """Expression de besoin (ENGAGEMENTS-PROJETS) via le réseau — la
    validation fait automatiquement basculer vers un Bon de commande
    (même moteur que l'application de bureau)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.expression_id_selectionnee = None

        ttk.Label(self, text="EXPRESSION DE BESOIN", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        header = ttk.LabelFrame(self, text="Nouvelle expression de besoin")
        header.pack(fill="x", padx=16, pady=4)
        ttk.Label(header, text="Numéro :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.numero_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.numero_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(header, text="Date (JJ/MM/AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(header, textvariable=self.date_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(header, text="Demandeur :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.demandeur_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.demandeur_var, width=18).grid(row=0, column=5, padx=4)
        ttk.Button(header, text="Créer", command=self.creer).grid(row=0, column=6, padx=12)

        ligne_frame = ttk.LabelFrame(self, text="Lignes (une fois créée, sélectionnée dans la liste)")
        ligne_frame.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(ligne_frame, text="Libellé :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.libelle_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.libelle_var, width=30).grid(row=0, column=1, padx=4)
        ttk.Label(ligne_frame, text="Quantité :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.quantite_var = tk.StringVar(value="1")
        ttk.Entry(ligne_frame, textvariable=self.quantite_var, width=10).grid(row=0, column=3, padx=4)
        ttk.Label(ligne_frame, text="Unité :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.unite_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.unite_var, width=10).grid(row=0, column=5, padx=4)
        ttk.Button(ligne_frame, text="Ajouter la ligne", command=self.ajouter_ligne).grid(row=0, column=6, padx=12)

        ttk.Button(self, text="Valider (bascule en Bon de commande sur le serveur)",
                   command=self.valider).pack(anchor="w", padx=16, pady=8)

        ttk.Separator(self).pack(fill="x", padx=16, pady=4)
        ttk.Label(self, text="Expressions existantes", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(2, 4))
        cols = ("id", "numero", "date", "demandeur", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, h, w in zip(cols, ["ID", "Numéro", "Date", "Demandeur", "Statut"], [40, 100, 90, 200, 100]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def creer(self):
        if not self.numero_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le numéro est obligatoire.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        eid = self._appeler("create_expression_besoin", self.numero_var.get(), date_str,
                             demandeur=self.demandeur_var.get().strip())
        if eid is APPEL_ECHEC:
            return
        self.expression_id_selectionnee = eid
        self.numero_var.set("")
        self.refresh()

    def ajouter_ligne(self):
        if not self.expression_id_selectionnee:
            messagebox.showinfo("Info", "Créez ou sélectionnez d'abord une expression dans la liste.", parent=self)
            return
        if not self.libelle_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le libellé est obligatoire.", parent=self)
            return
        try:
            qte = float(self.quantite_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "La quantité doit être un nombre.", parent=self)
            return
        r = self._appeler("add_ligne_expression_besoin", self.expression_id_selectionnee,
                           self.libelle_var.get(), qte, unite=self.unite_var.get() or None)
        if r is APPEL_ECHEC:
            return
        self.libelle_var.set(""); self.quantite_var.set("1"); self.unite_var.set("")
        messagebox.showinfo("Ajouté", "Ligne ajoutée.", parent=self)

    def valider(self):
        if not self.expression_id_selectionnee:
            messagebox.showinfo("Info", "Sélectionnez d'abord une expression dans la liste.", parent=self)
            return
        if not messagebox.askyesno("Valider", "Cette expression va basculer en Bon de commande. Continuer ?",
                                    parent=self):
            return
        r = self._appeler("valider_expression_besoin", self.expression_id_selectionnee)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Validée", "Bon de commande créé sur le serveur (menu Bon de commande).", parent=self)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.expression_id_selectionnee = int(self.tree.item(sel[0], "values")[0])

    def refresh(self):
        expressions = self._appeler("list_expressions_besoin")
        if expressions is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for e in expressions:
            self.tree.insert("", "end", values=(
                e["id"], e["numero"], core.to_display_date(e["date_demande"]), e["demandeur"] or "", e["statut"]))


class RemoteBonCommandeTab(ttk.Frame):
    """Bon de commande (ENGAGEMENTS-PROJETS) via le réseau — la validation
    comptabilise directement l'achat, comme sur l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.bon_id_selectionne = None

        ttk.Label(self, text="BON DE COMMANDE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        header = ttk.LabelFrame(self, text="Nouveau bon de commande")
        header.pack(fill="x", padx=16, pady=4)
        ttk.Label(header, text="Numéro :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.numero_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.numero_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(header, text="Date (JJ/MM/AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(header, textvariable=self.date_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(header, text="Fournisseur (code) :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.fournisseur_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.fournisseur_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Button(header, text="Créer", command=self.creer).grid(row=0, column=6, padx=12)

        ligne_frame = ttk.LabelFrame(self, text="Lignes — un compte débiteur (charge ou immobilisation) est "
                                                  "OBLIGATOIRE pour pouvoir valider")
        ligne_frame.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(ligne_frame, text="Compte débiteur :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.compte_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.compte_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(ligne_frame, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.libelle_var, width=26).grid(row=0, column=3, padx=4)
        ttk.Label(ligne_frame, text="Quantité :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.quantite_var = tk.StringVar(value="1")
        ttk.Entry(ligne_frame, textvariable=self.quantite_var, width=8).grid(row=0, column=5, padx=4)
        ttk.Label(ligne_frame, text="Prix unitaire :").grid(row=0, column=6, sticky="w", padx=(12, 4))
        self.prix_var = tk.StringVar()
        ttk.Entry(ligne_frame, textvariable=self.prix_var, width=12).grid(row=0, column=7, padx=4)
        ttk.Button(ligne_frame, text="Ajouter la ligne", command=self.ajouter_ligne).grid(row=0, column=8, padx=12)

        ttk.Button(self, text="Valider (comptabilise + crée le Bordereau sur le serveur)",
                   command=self.valider).pack(anchor="w", padx=16, pady=8)

        ttk.Separator(self).pack(fill="x", padx=16, pady=4)
        ttk.Label(self, text="Bons de commande existants", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(2, 4))
        cols = ("id", "numero", "date", "fournisseur", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, h, w in zip(cols, ["ID", "Numéro", "Date", "Fournisseur", "Statut"], [40, 100, 90, 200, 100]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def creer(self):
        if not self.numero_var.get().strip():
            messagebox.showwarning("Champ manquant", "Le numéro est obligatoire.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        bid = self._appeler("create_ep_bon_commande", self.numero_var.get(), date_str,
                             fournisseur_code=self.fournisseur_var.get().strip())
        if bid is APPEL_ECHEC:
            return
        self.bon_id_selectionne = bid
        self.numero_var.set("")
        self.refresh()

    def ajouter_ligne(self):
        if not self.bon_id_selectionne:
            messagebox.showinfo("Info", "Créez ou sélectionnez d'abord un bon dans la liste.", parent=self)
            return
        compte = self.compte_var.get().strip()
        libelle = self.libelle_var.get().strip()
        if not compte or not libelle:
            messagebox.showwarning("Champ manquant", "Compte débiteur et libellé sont obligatoires.", parent=self)
            return
        try:
            qte = float(self.quantite_var.get() or 0)
            prix = float(self.prix_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Quantité et Prix unitaire doivent être des nombres.", parent=self)
            return
        r = self._appeler("add_ligne_ep_bon_commande", self.bon_id_selectionne, libelle, qte,
                           prix_unitaire=prix, compte_charge=compte)
        if r is APPEL_ECHEC:
            return
        self.compte_var.set(""); self.libelle_var.set(""); self.quantite_var.set("1"); self.prix_var.set("")
        messagebox.showinfo("Ajoutée", "Ligne ajoutée.", parent=self)

    def valider(self):
        if not self.bon_id_selectionne:
            messagebox.showinfo("Info", "Sélectionnez d'abord un bon dans la liste.", parent=self)
            return
        if not messagebox.askyesno("Valider ce bon de commande",
                                    "Le bon va être comptabilisé sur le serveur ET un Bordereau de livraison "
                                    "sera créé. Continuer ?", parent=self):
            return
        r = self._appeler("valider_ep_bon_commande", self.bon_id_selectionne)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Validé", "Bon de commande comptabilisé sur le serveur.", parent=self)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.bon_id_selectionne = int(self.tree.item(sel[0], "values")[0])

    def refresh(self):
        bons = self._appeler("list_ep_bons_commande")
        if bons is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for b in bons:
            self.tree.insert("", "end", values=(
                b["id"], b["numero"], core.to_display_date(b["date_commande"]), b.get("fournisseur_code") or "",
                b["statut"]))


class RemoteRecouvrementTab(ttk.Frame):
    """Recouvrement (COMMERCIAL) via le réseau — balance âgée des créances
    clients, avec enregistrement du paiement."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="RECOUVREMENT — BALANCE ÂGÉE", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("client", "0_30", "31_60", "61_90", "plus_90", "total")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for c, h, w in zip(cols, ["Client", "0-30 j", "31-60 j", "61-90 j", "> 90 j", "Total dû"],
                           [280, 120, 120, 120, 120, 140]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c == "client" else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        clients = self._appeler("compute_balance_agee")
        if clients is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in clients:
            tranches = c.get("tranches", {})
            self.tree.insert("", "end", values=(
                c["raison_sociale"], fmt_cfa(tranches.get("0-30", 0)), fmt_cfa(tranches.get("31-60", 0)),
                fmt_cfa(tranches.get("61-90", 0)), fmt_cfa(tranches.get(">90", 0)), fmt_cfa(c.get("total", 0))))


class RemoteMargesTab(ttk.Frame):
    """Marges bénéficiaires (COMMERCIAL) via le réseau — mêmes indicateurs
    que la Liasse fiscale (marge commerciale, valeur ajoutée, résultat)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=16, pady=16)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        cr = self._appeler("compute_liasse_resultat")
        if cr is APPEL_ECHEC:
            return
        label_ca = "Chiffre d'affaires (XB)"
        label_re = "Résultat d'exploitation (XE)"
        lines = [
            "MARGES BÉNÉFICIAIRES", "=" * 60, "",
            f"  {'Ventes de marchandises (TA)':<45} {cr['TA']:>14,.2f}",
            f"  {'Achats de marchandises (RA)':<45} {-cr['RA']:>14,.2f}",
            f"  {'MARGE COMMERCIALE (XA)':<45} {cr['XA']:>14,.2f}", "",
            f"  {label_ca:<45} {cr['XB']:>14,.2f}",
            f"  {'VALEUR AJOUTÉE (XC)':<45} {cr['XC']:>14,.2f}",
            f"  {label_re:<45} {cr['XE']:>14,.2f}",
            f"  {'RÉSULTAT NET (XI)':<45} {cr['XI']:>14,.2f}",
        ]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class RemoteContratsTab(ttk.Frame):
    """Contrats fournisseurs (ENGAGEMENTS-PROJETS) via le réseau — suivi
    des délais de livraison et paiement."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote

        ttk.Label(self, text="CONTRATS FOURNISSEURS", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        form = ttk.LabelFrame(self, text="Nouvelle commande / contrat")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Fournisseur (code) :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.fournisseur_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.fournisseur_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="N° Pièce :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.piece_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.piece_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Libellé :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.libelle_var, width=26).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Montant :").grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.montant_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.montant_var, width=14).grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Label(form, text="Date commande (JJ/MM/AAAA) :").grid(row=1, column=2, sticky="w", padx=(12, 4), pady=(4, 0))
        self.date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(form, textvariable=self.date_var, width=12).grid(row=1, column=3, padx=4, pady=(4, 0))
        ttk.Button(form, text="Ajouter", command=self.add).grid(row=1, column=5, padx=4, pady=(4, 0))

        cols = ("id", "fournisseur", "piece", "libelle", "montant", "date")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, h, w in zip(cols, ["ID", "Fournisseur", "Pièce", "Libellé", "Montant", "Date"],
                           [40, 220, 90, 260, 120, 90]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def add(self):
        if not self.fournisseur_var.get().strip() or not self.piece_var.get().strip():
            messagebox.showwarning("Champ manquant", "Fournisseur et N° pièce sont obligatoires.", parent=self)
            return
        try:
            montant = float(self.montant_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le montant doit être un nombre.", parent=self)
            return
        date_str = core.to_iso_date(self.date_var.get().strip())
        r = self._appeler("add_commande", self.fournisseur_var.get().strip(), self.piece_var.get().strip(),
                           self.libelle_var.get().strip(), montant, date_str)
        if r is APPEL_ECHEC:
            return
        self.piece_var.set(""); self.libelle_var.set(""); self.montant_var.set("")
        self.refresh()

    def refresh(self):
        commandes = self._appeler("list_commandes")
        if commandes is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in commandes:
            self.tree.insert("", "end", values=(
                c["id"], c["raison_sociale"], c["piece"], c["libelle"], fmt_cfa(c["montant"]),
                core.to_display_date(c["date_commande"])))


class RemoteBordereauLivraisonTab(ttk.Frame):
    """Bordereau de livraison (ENGAGEMENTS-PROJETS) via le réseau —
    consultation et confirmation de réception (quantités livrées)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.bordereau_id_selectionne = None

        ttk.Label(self, text="BORDEREAU DE LIVRAISON", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))

        cols = ("id", "numero", "date", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c, h, w in zip(cols, ["ID", "Numéro", "Date", "Statut"], [40, 120, 100, 100]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="x", padx=16, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ttk.Label(self, text="Lignes (quantités commandées / livrées)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=16)
        self.tree_lignes = ttk.Treeview(self, columns=("libelle", "qte_cmd", "qte_liv", "unite"),
                                         show="headings", height=10)
        for c, h, w in zip(("libelle", "qte_cmd", "qte_liv", "unite"),
                           ["Libellé", "Qté commandée", "Qté livrée", "Unité"], [300, 120, 120, 80]):
            self.tree_lignes.heading(c, text=h)
            self.tree_lignes.column(c, width=w, anchor="w")
        self.tree_lignes.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        ttk.Button(self, text="Valider la réception (confirme les quantités livrées)",
                   command=self.valider).pack(anchor="w", padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.bordereau_id_selectionne = int(self.tree.item(sel[0], "values")[0])
        self._refresh_lignes()

    def _refresh_lignes(self):
        for row in self.tree_lignes.get_children():
            self.tree_lignes.delete(row)
        if not self.bordereau_id_selectionne:
            return
        lignes = self._appeler("list_lignes_bordereau_livraison", self.bordereau_id_selectionne)
        if lignes is APPEL_ECHEC:
            return
        for l in lignes:
            self.tree_lignes.insert("", "end", values=(
                l["libelle"], f"{l['quantite_commandee']:g}", f"{l['quantite_livree']:g}", l["unite"] or ""))

    def valider(self):
        if not self.bordereau_id_selectionne:
            messagebox.showinfo("Info", "Sélectionnez d'abord un bordereau.", parent=self)
            return
        r = self._appeler("valider_bordereau_livraison", self.bordereau_id_selectionne)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Validé", "Réception confirmée sur le serveur.", parent=self)
        self.refresh()

    def refresh(self):
        bordereaux = self._appeler("list_bordereaux_livraison")
        if bordereaux is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for b in bordereaux:
            self.tree.insert("", "end", values=(
                b["id"], b["numero"], core.to_display_date(b["date_livraison"]), b["statut"]))


class RemoteAmortissementsTab(ttk.Frame):
    """Taux d'amortissement par catégorie (IMMOBILISATIONS) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="AMORTISSEMENTS — TAUX PAR CATÉGORIE", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        self.tree = ttk.Treeview(self, columns=("categorie", "taux"), show="headings", height=12)
        self.tree.heading("categorie", text="Catégorie")
        self.tree.heading("taux", text="Taux (%)")
        self.tree.column("categorie", width=350, anchor="w")
        self.tree.column("taux", width=100, anchor="e")
        self.tree.pack(fill="x", padx=16, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Nouveau taux (%) pour la catégorie sélectionnée :").pack(side="left")
        self.taux_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.taux_var, width=8).pack(side="left", padx=8)
        ttk.Button(form, text="Enregistrer", command=self.enregistrer).pack(side="left")
        self.selected_categorie = None
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_categorie = v[0]
        self.taux_var.set(v[1])

    def enregistrer(self):
        if not self.selected_categorie:
            messagebox.showinfo("Info", "Sélectionnez d'abord une catégorie.", parent=self)
            return
        try:
            taux = float(self.taux_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le taux doit être un nombre.", parent=self)
            return
        r = self._appeler("set_taux_amortissement", self.selected_categorie, taux)
        if r is APPEL_ECHEC:
            return
        self.refresh()

    def refresh(self):
        taux = self._appeler("list_taux_amortissement")
        if taux is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for t in taux:
            self.tree.insert("", "end", values=(t["categorie"], f"{t['taux_pct']:g}"))


class RemoteParcAutoTab(ttk.Frame):
    """Parc auto (TRANSPORT) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None
        ttk.Label(self, text="PARC AUTO", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        form = ttk.LabelFrame(self, text="Véhicule")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Immatriculation :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.immat_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.immat_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Marque :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.marque_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.marque_var, width=16).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Modèle :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.modele_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.modele_var, width=16).grid(row=0, column=5, padx=4)
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left", padx=8)
        cols = ("id", "immat", "marque", "modele")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["ID", "Immatriculation", "Marque", "Modèle"], [40, 140, 160, 160]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_id = self.tree.item(sel[0], "values")[0]

    def add(self):
        if not self.immat_var.get().strip():
            messagebox.showwarning("Champ manquant", "L'immatriculation est obligatoire.", parent=self)
            return
        r = self._appeler("add_vehicule", self.immat_var.get(), marque=self.marque_var.get(),
                           modele=self.modele_var.get())
        if r is APPEL_ECHEC:
            return
        self.immat_var.set(""); self.marque_var.set(""); self.modele_var.set("")
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord un véhicule.", parent=self)
            return
        r = self._appeler("delete_vehicule", self.selected_id)
        if r is APPEL_ECHEC:
            return
        self.refresh()

    def refresh(self):
        vehicules = self._appeler("list_vehicules")
        if vehicules is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for v in vehicules:
            self.tree.insert("", "end", values=(v["id"], v["immatriculation"], v["marque"] or "", v["modele"] or ""))


class RemoteMissionsTab(ttk.Frame):
    """Missions (TRANSPORT) via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None
        ttk.Label(self, text="MISSIONS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        form = ttk.LabelFrame(self, text="Mission")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Destination :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.destination_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.destination_var, width=20).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Chauffeur :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.chauffeur_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.chauffeur_var, width=18).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Motif :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.motif_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.motif_var, width=20).grid(row=0, column=5, padx=4)
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left", padx=8)
        cols = ("id", "destination", "chauffeur", "motif")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["ID", "Destination", "Chauffeur", "Motif"], [40, 200, 180, 220]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_id = self.tree.item(sel[0], "values")[0]

    def add(self):
        if not self.destination_var.get().strip():
            messagebox.showwarning("Champ manquant", "La destination est obligatoire.", parent=self)
            return
        r = self._appeler("add_mission", self.destination_var.get(), chauffeur=self.chauffeur_var.get(),
                           motif=self.motif_var.get())
        if r is APPEL_ECHEC:
            return
        self.destination_var.set(""); self.chauffeur_var.set(""); self.motif_var.set("")
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord une mission.", parent=self)
            return
        r = self._appeler("delete_mission", self.selected_id)
        if r is APPEL_ECHEC:
            return
        self.refresh()

    def refresh(self):
        missions = self._appeler("list_missions")
        if missions is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for m in missions:
            self.tree.insert("", "end", values=(m["id"], m["destination"], m["chauffeur"] or "", m["motif"] or ""))


class RemotePiecesRechangeTab(ttk.Frame):
    """Pièces de rechange (TRANSPORT/MAINTENANCE-QUALITÉ, partagé) via le
    réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        self.selected_id = None
        ttk.Label(self, text="PIÈCES DE RECHANGE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        form = ttk.LabelFrame(self, text="Pièce")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Désignation :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.designation_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.designation_var, width=24).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Quantité stock :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.qte_var = tk.StringVar(value="0")
        ttk.Entry(form, textvariable=self.qte_var, width=10).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Coût unitaire :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.cout_var = tk.StringVar(value="0")
        ttk.Entry(form, textvariable=self.cout_var, width=12).grid(row=0, column=5, padx=4)
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left", padx=8)
        cols = ("id", "designation", "qte", "cout")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        for c, h, w in zip(cols, ["ID", "Désignation", "Qté stock", "Coût unitaire"], [40, 300, 100, 120]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_id = self.tree.item(sel[0], "values")[0]

    def add(self):
        if not self.designation_var.get().strip():
            messagebox.showwarning("Champ manquant", "La désignation est obligatoire.", parent=self)
            return
        try:
            qte = float(self.qte_var.get() or 0)
            cout = float(self.cout_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Quantité et coût doivent être des nombres.", parent=self)
            return
        r = self._appeler("add_piece_rechange", self.designation_var.get(), quantite_stock=qte, cout_unitaire=cout)
        if r is APPEL_ECHEC:
            return
        self.designation_var.set(""); self.qte_var.set("0"); self.cout_var.set("0")
        self.refresh()

    def delete_sel(self):
        if not self.selected_id:
            messagebox.showinfo("Info", "Sélectionnez d'abord une pièce.", parent=self)
            return
        r = self._appeler("delete_piece_rechange", self.selected_id)
        if r is APPEL_ECHEC:
            return
        self.refresh()

    def refresh(self):
        pieces = self._appeler("list_pieces_rechange")
        if pieces is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in pieces:
            self.tree.insert("", "end", values=(
                p["id"], p["designation"], f"{p['quantite_stock']:g}", fmt_cfa(p["cout_unitaire"])))


class RemoteReparationsTab(ttk.Frame):
    """Réparations (TRANSPORT) via le réseau — consultation."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="RÉPARATIONS", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("id", "description", "date", "garage")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for c, h, w in zip(cols, ["ID", "Description", "Date", "Garage"], [40, 320, 100, 200]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        reparations = self._appeler("list_reparations")
        if reparations is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in reparations:
            self.tree.insert("", "end", values=(
                r["id"], r["description"], core.to_display_date(r.get("date_reparation") or ""),
                r.get("garage") or ""))


class RemoteSimplePlanTab(ttk.Frame):
    """Écran générique code/libellé (+ montant/unité optionnels) via le
    réseau — réutilisé pour Plan analytique, Plan budgétaire, Plan
    bailleurs de fonds, Taux TVA, Taux retenue — même principe que
    _SimplePlanTab dans l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection, titre, list_fn, add_fn, delete_fn,
                 code_label="Code", extra_field=None):
        super().__init__(parent)
        self.remote = remote
        self.titre = titre
        self.list_fn_name = list_fn
        self.add_fn_name = add_fn
        self.delete_fn_name = delete_fn
        self.extra_field = extra_field  # None, "unite", ou "montant"
        self.selected_code = None

        ttk.Label(self, text=titre, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        form = ttk.LabelFrame(self, text="Élément")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text=f"{code_label} :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(form, textvariable=self.code_var, width=16)
        self.code_entry.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.label_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.label_var, width=40).grid(row=0, column=3, padx=4)
        if extra_field:
            libelle_champ = "Unité (L, Kw, H...)" if extra_field == "unite" else "Montant / Taux (%)"
            ttk.Label(form, text=f"{libelle_champ} :").grid(row=0, column=4, sticky="w", padx=(12, 4))
            self.extra_var = tk.StringVar()
            ttk.Entry(form, textvariable=self.extra_var, width=12).grid(row=0, column=5, padx=4)
        else:
            self.extra_var = None

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=6)
        ttk.Button(btns, text="Ajouter", command=self.add).pack(side="left")
        ttk.Button(btns, text="Mettre à jour la sélection", command=self.update_sel).pack(side="left", padx=8)
        ttk.Button(btns, text="Supprimer la sélection", command=self.delete_sel).pack(side="left")
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=8)

        cols = ("code", "label", "extra") if extra_field else ("code", "label")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        self.tree.heading("code", text=code_label)
        self.tree.heading("label", text="Libellé")
        self.tree.column("code", width=140, anchor="w")
        self.tree.column("label", width=400, anchor="w")
        if extra_field:
            self.tree.heading("extra", text="Unité" if extra_field == "unite" else "Montant/Taux")
            self.tree.column("extra", width=120, anchor="e" if extra_field == "montant" else "w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.selected_code = v[0]
        self.code_var.set(v[0]); self.label_var.set(v[1])
        if self.extra_var is not None and len(v) > 2:
            self.extra_var.set(v[2])
        self.code_entry.configure(state="disabled")

    def clear_form(self):
        self.selected_code = None
        self.code_var.set(""); self.label_var.set("")
        if self.extra_var is not None:
            self.extra_var.set("")
        self.code_entry.configure(state="normal")

    def _extra_kwargs(self):
        if not self.extra_field:
            return {}
        raw = self.extra_var.get().strip()
        if self.extra_field == "unite":
            return {"unite": raw or None}
        try:
            return {"montant": float(raw) if raw else 0}
        except ValueError:
            messagebox.showerror("Erreur", "Le montant/taux doit être un nombre.", parent=self)
            return None

    def add(self):
        if not self.code_var.get().strip() or not self.label_var.get().strip():
            messagebox.showwarning("Champ manquant", "Code et libellé sont obligatoires.", parent=self)
            return
        kwargs = self._extra_kwargs()
        if kwargs is None:
            return
        r = self._appeler(self.add_fn_name, self.code_var.get(), self.label_var.get(), **kwargs)
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def update_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un élément.", parent=self)
            return
        kwargs = self._extra_kwargs()
        if kwargs is None:
            return
        r = self._appeler(self.add_fn_name, self.selected_code, self.label_var.get(), **kwargs)
        if r is APPEL_ECHEC:
            return
        self.clear_form()
        self.refresh()

    def delete_sel(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un élément.", parent=self)
            return
        if messagebox.askyesno("Confirmer", f"Supprimer « {self.selected_code} » ?", parent=self):
            r = self._appeler(self.delete_fn_name, self.selected_code)
            if r is APPEL_ECHEC:
                return
            self.clear_form()
            self.refresh()

    def refresh(self):
        items = self._appeler(self.list_fn_name)
        if items is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for it in items:
            if self.extra_field == "unite":
                self.tree.insert("", "end", values=(it["code"], it["label"], it.get("unite") or ""))
            elif self.extra_field == "montant":
                self.tree.insert("", "end", values=(it["code"], it["label"], fmt_cfa(it.get("montant"))))
            else:
                self.tree.insert("", "end", values=(it["code"], it["label"]))


class RemoteAnalytiquePeriodeTab(ttk.Frame):
    """Coûts analytiques par catégorie (Énergie, Maintenance) via le
    réseau — même principe que AnalytiquePeriodeTab dans l'application de
    bureau."""

    def __init__(self, parent, remote: RemoteConnection, titre, description, prefix):
        super().__init__(parent)
        self.remote = remote
        self.prefix = prefix
        ttk.Label(self, text=titre.upper(), font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Label(self, text=description, foreground="#595959", wraplength=1200, justify="left").pack(
            anchor="w", padx=16, pady=(0, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("code", "label", "debut", "periode", "fin")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        for c, h, w in zip(cols, ["Code", "Libellé", "Début période", "Charge période", "Cumul fin"],
                           [110, 260, 130, 130, 130]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("code", "label") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        items = self._appeler("compute_couts_analytiques_categorie", self.prefix)
        if items is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i in items:
            self.tree.insert("", "end", values=(
                i["code"], i["label"], fmt_cfa(i["solde_debut_periode"]),
                fmt_cfa(i["debit_periode"] - i["credit_periode"]), fmt_cfa(i["solde_fin_periode"])))


class RemoteProductionTab(ttk.Frame):
    """Fabrication / Production en lecture seule via le réseau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="PRODUCTION — FABRICATION", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("compte", "libelle", "debit", "credit", "solde")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=24)
        for c, h, w in zip(cols, ["Compte", "Libellé", "Débit", "Crédit", "Solde"], [90, 300, 130, 130, 130]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("compte", "libelle") else "e")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        lignes = self._appeler("compute_production")
        if lignes is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for l in lignes:
            self.tree.insert("", "end", values=(
                l["code"], l["label"], fmt_cfa(l["debit"]), fmt_cfa(l["credit"]), fmt_cfa(l["solde"])))


class RemoteExercicesTab(ttk.Frame):
    """Exercices comptables (clôture) via le réseau — consultation et
    clôture (report des soldes vers l'exercice suivant)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="EXERCICES COMPTABLES", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        ttk.Label(self, text=(
            "La clôture calcule les soldes de clôture de tous les comptes de bilan et les reporte comme "
            "soldes d'ouverture de l'exercice suivant. Cette action est IRRÉVERSIBLE."
        ), foreground="#B00020", wraplength=1100, justify="left").pack(anchor="w", padx=16, pady=(0, 8))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))
        cols = ("exercice", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        self.tree.heading("exercice", text="Exercice")
        self.tree.heading("statut", text="Statut")
        self.tree.column("exercice", width=140, anchor="w")
        self.tree.column("statut", width=140, anchor="w")
        self.tree.pack(fill="x", padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.selected_exercice = None
        ttk.Button(self, text="Clôturer l'exercice sélectionné (reporte les soldes)",
                   command=self.cloturer).pack(anchor="w", padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_exercice = self.tree.item(sel[0], "values")[0]

    def cloturer(self):
        if not self.selected_exercice:
            messagebox.showinfo("Info", "Sélectionnez d'abord un exercice.", parent=self)
            return
        if not messagebox.askyesno(
            "Clôturer cet exercice",
            f"Clôturer définitivement l'exercice {self.selected_exercice} ? Cette action est IRRÉVERSIBLE.",
            parent=self,
        ):
            return
        r = self._appeler("close_exercice", self.selected_exercice)
        if r is APPEL_ECHEC:
            return
        messagebox.showinfo("Clôturé", f"Exercice {self.selected_exercice} clôturé sur le serveur.", parent=self)
        self.refresh()

    def refresh(self):
        exercices = self._appeler("list_exercices")
        if exercices is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for e in exercices:
            self.tree.insert("", "end", values=(e["exercice"], "Clôturé" if e["cloture"] else "Ouvert"))


class RemotePlaceholderTab(ttk.Frame):
    """Écran non encore défini — même principe que PlaceholderTab dans
    l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection, titre, message):
        super().__init__(parent)
        ttk.Label(self, text=titre.upper(), font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        ttk.Label(self, text=message, foreground="#595959", wraplength=1100, justify="left").pack(
            anchor="w", padx=16)


class RemoteSynchronisationTab(ttk.Frame):
    """Synchronisation — explique pourquoi cette opération de maintenance
    du schéma n'est pas exposée à distance (volontairement, pour la
    sécurité — voir server.py RPC_WHITELIST)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        ttk.Label(self, text="SYNCHRONISATION", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))
        ttk.Label(self, text=(
            "Cette opération de maintenance (mise à jour du schéma de la base de données) n'est "
            "volontairement pas exposée à distance, par sécurité — elle reste réservée à l'application "
            "de bureau ou au poste serveur directement. Le serveur applique déjà automatiquement toute "
            "mise à jour de schéma nécessaire à son propre démarrage."
        ), foreground="#595959", wraplength=1100, justify="left").pack(anchor="w", padx=16)


class RemoteOuvertureTab(ttk.Frame):
    """Soldes d'ouverture via le réseau — Débit/Crédit avec totaux et
    contrôle d'équilibre, même principe que l'application de bureau."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote

        ttk.Label(self, text="SOLDES D'OUVERTURE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(anchor="w", padx=16, pady=(0, 4))

        form = ttk.LabelFrame(self, text="Saisir / modifier un solde")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Compte :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.compte_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.compte_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Débit :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.debit_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.debit_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Crédit :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.credit_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.credit_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Button(form, text="Enregistrer", command=self.enregistrer).grid(row=0, column=6, padx=12)

        cols = ("code", "label", "debit", "credit")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22)
        headers = ["N° Compte", "Libellé", "Débit", "Crédit"]
        widths = [90, 380, 130, 130]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c in ("code", "label") else "e")
        self.tree.tag_configure("total", background="#1F4E78", foreground="white", font=("Segoe UI", 10, "bold"))
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)

        self.total_var = tk.StringVar()
        ttk.Label(self, textvariable=self.total_var, font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def enregistrer(self):
        compte = self.compte_var.get().strip()
        if not compte:
            messagebox.showwarning("Champ manquant", "Le compte est obligatoire.", parent=self)
            return
        try:
            debit = float(self.debit_var.get() or 0)
            credit = float(self.credit_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Débit et Crédit doivent être des nombres.", parent=self)
            return
        if debit and credit:
            messagebox.showwarning("Erreur", "Un compte est soit au débit, soit au crédit — pas les deux.",
                                    parent=self)
            return
        solde = debit - credit
        r = self._appeler("set_opening_balance", compte, solde)
        if r is APPEL_ECHEC:
            return
        self.compte_var.set(""); self.debit_var.set(""); self.credit_var.set("")
        self.refresh()

    def refresh(self):
        soldes = self._appeler("list_opening_balances")
        if soldes is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        total_debit = total_credit = 0.0
        for s in soldes:
            solde = s["solde"]
            debit = solde if solde > 0 else 0.0
            credit = -solde if solde < 0 else 0.0
            self.tree.insert("", "end", values=(
                s["code"], s["label"], fmt_cfa(debit) if debit else "", fmt_cfa(credit) if credit else ""))
            total_debit += debit
            total_credit += credit
        self.tree.insert("", "end", tags=("total",), values=(
            "", "TOTAL", fmt_cfa(total_debit), fmt_cfa(total_credit)))
        ecart = total_debit - total_credit
        etat = "Équilibré ✓" if abs(ecart) < 0.01 else "NON ÉQUILIBRÉ ✗"
        self.total_var.set(f"Total Débit : {fmt_cfa(total_debit)}   —   Total Crédit : {fmt_cfa(total_credit)}   "
                            f"—   {etat}")


class RemotePlanComptableTab(ttk.Frame):
    """Plan comptable en lecture seule via le réseau — recherche par code
    ou libellé (la création/modification de comptes reste réservée à
    l'application de bureau, opération structurante rarement nécessaire
    à distance)."""

    def __init__(self, parent, remote: RemoteConnection):
        super().__init__(parent)
        self.remote = remote
        ttk.Label(self, text="PLAN COMPTABLE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        search_bar = ttk.Frame(self)
        search_bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(search_bar, text="Rechercher (code ou libellé) :").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=6)
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())
        cols = ("code", "label", "classe")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=26)
        for c, h, w in zip(cols, ["Code", "Libellé", "Classe"], [110, 420, 80]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _appeler(self, fonction, *args, **kwargs):
        return appeler(self, self.remote, fonction, *args, **kwargs)

    def refresh(self):
        comptes = self._appeler("search_accounts", self.search_var.get().strip(), limit=300)
        if comptes is APPEL_ECHEC:
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in comptes:
            self.tree.insert("", "end", values=(c["code"], c["label"], c.get("classe", "")))


def main():
    login = LoginWindow()
    login.mainloop()
    if login.remote is None:
        return  # fenêtre fermée sans connexion réussie
    app = ClientApp(login.remote)
    app.mainloop()


if __name__ == "__main__":
    main()
