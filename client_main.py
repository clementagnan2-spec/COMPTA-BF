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
        if remote.ping():
            self.status_var.set("✓ Serveur joignable.")
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
    }

    def __init__(self, remote: RemoteConnection):
        super().__init__()
        self.remote = remote
        self.pages = {}
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


def main():
    login = LoginWindow()
    login.mainloop()
    if login.remote is None:
        return  # fenêtre fermée sans connexion réussie
    app = ClientApp(login.remote)
    app.mainloop()


if __name__ == "__main__":
    main()
