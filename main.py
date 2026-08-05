"""
main.py — Application de comptabilité SYSCOHADA autonome (Tkinter).

Navigation par menu (SAISIE, COMMERCE, PRODUCTION, ENGAGEMENTS-PROJETS,
ÉTATS ET RAPPORTS) : un seul panneau de contenu, qui change selon le menu
choisi. Les données sont stockées localement dans un fichier SQLite
(%LOCALAPPDATA%\\SaisieComptable\\comptabilite.db sous Windows).
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import date

import core


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Saisie Comptable SYSCOHADA")
        self.geometry("1200x720")
        self.conn = core.get_connection()

        # ---- Barre d'exercice comptable (toujours visible, en haut) ----
        top_bar = ttk.Frame(self, relief="raised", padding=4)
        top_bar.pack(fill="x", side="top")
        ttk.Label(top_bar, text="EXERCICE COMPTABLE :", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        self.exercice_var = tk.StringVar(value=core.get_current_exercice(self.conn))
        self.exercice_combo = ttk.Combobox(top_bar, textvariable=self.exercice_var, width=10, state="readonly")
        self.exercice_combo.pack(side="left", padx=4)
        self.exercice_combo.bind("<<ComboboxSelected>>", self._on_exercice_changed)
        ttk.Button(top_bar, text="+ Nouvel exercice", command=self._new_exercice).pack(side="left", padx=8)
        self.exercice_status_var = tk.StringVar()
        ttk.Label(top_bar, textvariable=self.exercice_status_var, foreground="#B00020",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=12)
        self._refresh_exercice_list()

        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages = {}

        def register(key, cls, *args):
            w = cls(self.content, self.conn, *args)
            w.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = w
            return w

        # ---- Instanciation de toutes les pages (une seule fois) ----
        register("saisie", SaisieTab)
        register("ouverture", OpeningBalancesTab)
        register("exercices", ExercicesTab, self)
        register("plan_comptable", PlanComptableTab)
        register("plan_analytique", PlanAnalytiqueTab)
        register("plan_budgetaire", PlanBudgetaireTab)
        register("plan_bailleur", PlanBailleurTab)
        register("stocks", StocksTab)
        register("production", ProductionTab)
        register("cr", CompteResultatTab)
        register("tft", TftTab)
        register("grand_livre", GrandLivreTab)
        register("balance", BalanceTab)
        register("bilan", BilanTab)
        register("liasse", LiasseFiscaleTab)
        register("ventes", VentesTab)
        register("clients", ClientsTab)
        register("marges", MargesTab)
        register("achats", AchatsTab)
        register("fournisseurs", FournisseursTab)
        register("contrats", ContratsTab)
        register("budget_exec", PlaceholderTab,
                 "Tableaux d'exécution budgétaire",
                 "Suivi budget prévisionnel vs réalisé, par ligne budgétaire et par projet.")
        register("impots", PlaceholderTab,
                 "Impôts", "Calcul et suivi des impôts (IS, TVA due/récupérable, retenues à la source...).")
        register("declarations_sociales", PlaceholderTab,
                 "Déclarations sociales", "Préparation des déclarations CNSS et assimilées.")
        register("rapprochements", PlaceholderTab,
                 "Rapprochements bancaires",
                 "Comparaison des relevés bancaires avec les comptes de trésorerie (521000/531000/570000).")

        # ---- Barre de menu ----
        menubar = tk.Menu(self)
        bold = ("Segoe UI", 9, "bold")

        def add_top_menu(label, items):
            m = tk.Menu(menubar, tearoff=0)
            for item_label, key in items:
                m.add_command(label=item_label, command=lambda k=key: self.show(k))
            menubar.add_cascade(label=label, menu=m)
            menubar.entryconfig(menubar.index("end"), font=bold)

        add_top_menu("SAISIE", [
            ("Saisie des écritures", "saisie"),
            ("Soldes d'ouverture", "ouverture"),
        ])
        add_top_menu("COMMERCE", [
            ("Ventes", "ventes"),
            ("Clients", "clients"),
            ("Stocks", "stocks"),
            ("Marges bénéficiaires", "marges"),
        ])
        add_top_menu("PRODUCTION", [
            ("Matières premières", "stocks"),
            ("Fabrication", "production"),
            ("Produits finis", "stocks"),
        ])
        add_top_menu("ENGAGEMENTS-PROJETS", [
            ("Achats", "achats"),
            ("Fournisseurs", "fournisseurs"),
            ("Contrats", "contrats"),
        ])
        add_top_menu("ÉTATS ET RAPPORTS", [
            ("Grand livre", "grand_livre"),
            ("Balance", "balance"),
            ("Bilan", "bilan"),
            ("Compte de résultat", "cr"),
            ("TFT", "tft"),
            ("Liasse fiscale", "liasse"),
            ("Tableaux d'exécution budgétaire", "budget_exec"),
            ("Impôts", "impots"),
            ("Déclarations sociales", "declarations_sociales"),
            ("Rapprochements bancaires", "rapprochements"),
        ])
        add_top_menu("PARAMÈTRES", [
            ("Exercices comptables (clôture)", "exercices"),
            ("Plan comptable", "plan_comptable"),
            ("Plan analytique", "plan_analytique"),
            ("Plan budgétaire", "plan_budgetaire"),
            ("Plan bailleurs de fonds", "plan_bailleur"),
        ])
        self.config(menu=menubar)

        self.show("saisie")

    def _refresh_exercice_list(self):
        exercices = core.list_exercices(self.conn)
        values = [e["exercice"] + (" (clôturé)" if e["cloture"] else "") for e in exercices]
        self.exercice_combo["values"] = values
        current = core.get_current_exercice(self.conn)
        match = next((v for v in values if v.startswith(current)), current)
        self.exercice_var.set(match)
        if core.is_exercice_cloture(self.conn, current):
            self.exercice_status_var.set("⚠ Cet exercice est clôturé (lecture seule).")
        else:
            self.exercice_status_var.set("")

    def _on_exercice_changed(self, event=None):
        raw = self.exercice_var.get().split(" ")[0]
        core.set_current_exercice(self.conn, raw)
        self._refresh_exercice_list()
        self.refresh_current_page()

    def _new_exercice(self):
        current = core.get_current_exercice(self.conn)
        suggestion = str(int(current) + 1)
        new_ex = simpledialog.askstring("Nouvel exercice", "Année de l'exercice (AAAA) :",
                                         initialvalue=suggestion, parent=self)
        if not new_ex:
            return
        core.set_current_exercice(self.conn, new_ex.strip())
        self._refresh_exercice_list()
        self.refresh_current_page()

    def refresh_current_page(self):
        for page in self.pages.values():
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception:
                    pass

    def show(self, key):
        page = self.pages[key]
        page.tkraise()
        if hasattr(page, "refresh"):
            page.refresh()


class SaisieTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.selected_id = None
        self.pending_piece = None
        self._build()
        self.refresh()

    def _default_date(self):
        """Aujourd'hui si son année correspond à l'exercice courant, sinon le
        1er janvier de l'exercice courant."""
        exercice = core.get_current_exercice(self.conn)
        today = date.today()
        if str(today.year) == exercice:
            return today.strftime("%d/%m/%Y")
        return f"01/01/{exercice}"

    def _build(self):
        form = ttk.LabelFrame(self, text="Écriture (partie double : compte débiteur ET compte créditeur obligatoires)")
        form.pack(fill="x", padx=8, pady=8)

        labels = ["Date (JJ/MM/AAAA)", "N° Pièce", "Journal",
                  "Compte débiteur", "Compte créditeur", "Montant",
                  "Tiers", "Libellé", "Fournisseur",
                  "Code analytique (ex: AN-FAB)", "Code budgétaire", "Code bailleur", "Quantité"]
        self.vars = {k: tk.StringVar() for k in labels}
        self.vars["Date (JJ/MM/AAAA)"].set(self._default_date())

        for i, lbl in enumerate(labels):
            r, c = divmod(i, 3)
            ttk.Label(form, text=lbl).grid(row=r * 2, column=c, sticky="w", padx=4, pady=(4, 0))
            if lbl == "Compte débiteur":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<KeyRelease>", lambda e: self._on_compte_keyrelease("Compte débiteur"))
                widget.bind("<<ComboboxSelected>>", lambda e: self._show_account_labels())
                widget.bind("<FocusOut>", lambda e: self._validate_compte_field("Compte débiteur"))
                self.compte_debit_combo = widget
            elif lbl == "Compte créditeur":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<KeyRelease>", lambda e: self._on_compte_keyrelease("Compte créditeur"))
                widget.bind("<<ComboboxSelected>>", lambda e: self._show_account_labels())
                widget.bind("<FocusOut>", lambda e: self._validate_compte_field("Compte créditeur"))
                self.compte_credit_combo = widget
            elif lbl == "Journal":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22,
                                       values=["AC", "VE", "OD", "BQ", "CA"])
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
            elif lbl == "Fournisseur":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<KeyRelease>", self._on_fournisseur_keyrelease)
                widget.bind("<FocusOut>", lambda e: self._validate_fournisseur_field())
                self.fournisseur_combo = widget
                self._refresh_fournisseur_values()
            elif lbl == "Code analytique (ex: AN-FAB)":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<FocusOut>", lambda e: self._validate_plan_field(
                    "Code analytique (ex: AN-FAB)", "analytique"))
                self.analytique_combo = widget
                self._refresh_plan_values("analytique")
            elif lbl == "Code budgétaire":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<FocusOut>", lambda e: self._validate_plan_field(
                    "Code budgétaire", "budgetaire"))
                self.budgetaire_combo = widget
                self._refresh_plan_values("budgetaire")
            elif lbl == "Code bailleur":
                widget = ttk.Combobox(form, textvariable=self.vars[lbl], width=22)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
                widget.bind("<FocusOut>", lambda e: self._validate_plan_field(
                    "Code bailleur", "bailleur"))
                self.bailleur_combo = widget
                self._refresh_plan_values("bailleur")
            else:
                widget = ttk.Entry(form, textvariable=self.vars[lbl], width=24)
                widget.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))

        self.account_label_var = tk.StringVar()
        ttk.Label(form, textvariable=self.account_label_var, foreground="#1F4E78").grid(
            row=10, column=0, columnspan=3, sticky="w", padx=4)

        self.balance_var = tk.StringVar()
        self.balance_label = ttk.Label(form, textvariable=self.balance_var, foreground="#B00020",
                                        font=("Segoe UI", 9, "bold"), wraplength=1000)
        self.balance_label.grid(row=10, column=1, columnspan=2, sticky="w", padx=4)

        btns = ttk.Frame(form)
        btns.grid(row=11, column=0, columnspan=3, sticky="w", pady=6, padx=4)
        ttk.Button(btns, text="Ajouter (écriture équilibrée)", command=self.add_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Enregistrer modification", command=self.update_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Supprimer", command=self.delete_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=2)

        import_bar = ttk.Frame(self)
        import_bar.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(import_bar, text="Importer des écritures (.xlsx)", command=self.import_xlsx).pack(side="left", padx=2)
        ttk.Button(import_bar, text="Télécharger un modèle (.xlsx)", command=self.download_template).pack(side="left", padx=2)
        ttk.Label(import_bar, text=(
            "Pour les volumes importants : préparez un fichier avec les colonnes Date, N° Pièce, "
            "Journal, N° Compte, Tiers, Libellé, Débit, Crédit, Quantité, Code analytique, Code "
            "budgétaire, Code bailleur (l'ordre n'a pas d'importance), puis importez-le d'un coup. "
            "(L'import accepte un compte par ligne comme avant ; c'est le formulaire ci-dessus qui "
            "impose désormais la paire débit/crédit.)"
        ), foreground="#595959", wraplength=850).pack(side="left", padx=10)

        cols = ("id", "date", "piece", "journal", "compte", "libelle_compte",
                "tiers", "libelle", "debit", "credit", "quantite", "analytique", "budget", "bailleur", "fournisseur")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headers = ["ID", "Date", "Pièce", "Journal", "Compte", "Libellé du compte",
                   "Tiers", "Libellé écriture", "Débit", "Crédit", "Qté", "Analytique", "Budget", "Bailleur", "Fournisseur"]
        widths = [40, 90, 80, 60, 70, 170, 90, 150, 75, 75, 55, 80, 80, 80, 100]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        totals = ttk.Frame(self)
        totals.pack(fill="x", padx=8, pady=(0, 8))
        self.totals_var = tk.StringVar()
        ttk.Label(totals, textvariable=self.totals_var, font=("Segoe UI", 10, "bold")).pack(side="left")

    def _extract_code(self, raw):
        raw = (raw or "").strip()
        return raw.split(" — ", 1)[0].strip() if " — " in raw else raw

    def _on_compte_keyrelease(self, field, event=None):
        combo = self.compte_debit_combo if field == "Compte débiteur" else self.compte_credit_combo
        query = self._extract_code(self.vars[field].get())
        if query:
            matches = core.search_accounts(self.conn, query, limit=30)
            combo["values"] = [f"{m['code']} — {m['label']}" for m in matches]
        self._show_account_labels()

    def _validate_compte_field(self, field):
        """Force un compte valide : propose de créer le compte ou de choisir dans la liste."""
        code = self._extract_code(self.vars[field].get())
        if not code:
            return
        if core.account_exists(self.conn, code):
            return
        if messagebox.askyesno(
            "Compte introuvable",
            f"Le compte « {code} » n'existe pas dans le Plan comptable.\n\n"
            f"Voulez-vous le créer maintenant ? (Non pour effacer et choisir un compte existant)"
        ):
            label = simpledialog.askstring("Nouveau compte", f"Libellé du compte « {code} » :", parent=self)
            if not label:
                self.vars[field].set("")
                return
            core.add_account(self.conn, code, label)
        else:
            self.vars[field].set("")
        self._show_account_labels()

    def _show_account_labels(self, event=None):
        d = self._extract_code(self.vars["Compte débiteur"].get())
        c = self._extract_code(self.vars["Compte créditeur"].get())
        parts = []
        if d:
            parts.append(f"Débit {d} : {core.get_account_label(self.conn, d)}")
        if c:
            parts.append(f"Crédit {c} : {core.get_account_label(self.conn, c)}")
        self.account_label_var.set("   |   ".join(parts))

    def _refresh_fournisseur_values(self):
        items = core.list_fournisseurs(self.conn)
        self.fournisseur_combo["values"] = [f"{f['code']} — {f['raison_sociale']}" for f in items]

    def _on_fournisseur_keyrelease(self, event=None):
        query = self._extract_code(self.vars["Fournisseur"].get())
        if query:
            items = core.list_fournisseurs(self.conn, query)
            self.fournisseur_combo["values"] = [f"{f['code']} — {f['raison_sociale']}" for f in items]

    def _validate_fournisseur_field(self):
        code = self._extract_code(self.vars["Fournisseur"].get())
        if not code or core.fournisseur_exists(self.conn, code):
            return
        if messagebox.askyesno(
            "Fournisseur introuvable",
            f"Le fournisseur « {code} » n'existe pas.\n\n"
            f"Voulez-vous le créer maintenant ? (Non pour effacer et choisir dans la liste existante)"
        ):
            raison = simpledialog.askstring("Nouveau fournisseur", f"Raison sociale pour « {code} » :", parent=self)
            if not raison:
                self.vars["Fournisseur"].set("")
                return
            core.add_fournisseur(self.conn, code, raison)
            self._refresh_fournisseur_values()
        else:
            self.vars["Fournisseur"].set("")

    def _refresh_plan_values(self, plan):
        if plan == "analytique":
            items = core.list_analytic_codes(self.conn)
            self.analytique_combo["values"] = [f"{i['code']} — {i['label']}" for i in items]
        elif plan == "budgetaire":
            items = core.list_budget_codes(self.conn)
            self.budgetaire_combo["values"] = [f"{i['code']} — {i['label']}" for i in items]
        elif plan == "bailleur":
            items = core.list_donor_codes(self.conn)
            self.bailleur_combo["values"] = [f"{i['code']} — {i['label']}" for i in items]

    def _validate_plan_field(self, var_key, plan):
        raw = self.vars[var_key].get().strip()
        code = raw.split(" — ", 1)[0].strip() if " — " in raw else raw
        if not code:
            return
        exists_fn = {"analytique": core.analytic_code_exists,
                     "budgetaire": core.budget_code_exists,
                     "bailleur": core.donor_code_exists}[plan]
        if exists_fn(self.conn, code):
            return
        plan_name = {"analytique": "Plan analytique", "budgetaire": "Plan budgétaire",
                     "bailleur": "Plan bailleurs de fonds"}[plan]
        if messagebox.askyesno(
            "Code introuvable",
            f"Le code « {code} » n'existe pas dans le {plan_name}.\n\n"
            f"Voulez-vous le créer maintenant ? (Non pour effacer et choisir dans la liste existante)"
        ):
            label = simpledialog.askstring("Nouveau code", f"Libellé pour « {code} » :", parent=self)
            if not label:
                self.vars[var_key].set("")
                return
            if plan == "analytique":
                core.add_analytic_code(self.conn, code, label)
            elif plan == "budgetaire":
                core.add_budget_code(self.conn, code, label)
            elif plan == "bailleur":
                core.add_donor_code(self.conn, code, label)
            self.vars[var_key].set(code)
            self._refresh_plan_values(plan)
        else:
            self.vars[var_key].set("")

    def _get_form(self):
        try:
            montant = float(self.vars["Montant"].get() or 0)
            quantite = float(self.vars["Quantité"].get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Montant et Quantité doivent être des nombres.")
            return None
        return dict(
            date_str=core.to_iso_date(self.vars["Date (JJ/MM/AAAA)"].get().strip()),
            piece=self.vars["N° Pièce"].get().strip(),
            journal=self.vars["Journal"].get().strip(),
            compte_debit=self._extract_code(self.vars["Compte débiteur"].get()),
            compte_credit=self._extract_code(self.vars["Compte créditeur"].get()),
            montant=montant,
            tiers=self.vars["Tiers"].get().strip(),
            libelle=self.vars["Libellé"].get().strip(),
            analytic_code=self._extract_code(self.vars["Code analytique (ex: AN-FAB)"].get()),
            budget_code=self._extract_code(self.vars["Code budgétaire"].get()),
            donor_code=self._extract_code(self.vars["Code bailleur"].get()),
            fournisseur_code=self._extract_code(self.vars["Fournisseur"].get()),
            quantite=quantite,
        )

    def add_entry(self):
        data = self._get_form()
        if not data:
            return
        missing = []
        if not data["date_str"]:
            missing.append("Date")
        if not data["piece"]:
            missing.append("N° Pièce")
        if not data["compte_debit"]:
            missing.append("Compte débiteur")
        if not data["compte_credit"]:
            missing.append("Compte créditeur")
        if not data["montant"] or data["montant"] <= 0:
            missing.append("Montant (> 0)")
        if missing:
            messagebox.showwarning(
                "Champs manquants",
                "Le principe de la partie double impose de renseigner ensemble le compte "
                "débiteur ET le compte créditeur pour un même montant.\n\n"
                "Champs manquants : " + ", ".join(missing)
            )
            return
        if not core.account_exists(self.conn, data["compte_debit"]):
            messagebox.showerror("Compte invalide", f"Le compte débiteur « {data['compte_debit']} » "
                                                      f"n'existe pas dans le Plan comptable. Créez-le d'abord "
                                                      f"(quittez le champ pour être invité à le créer).")
            return
        if not core.account_exists(self.conn, data["compte_credit"]):
            messagebox.showerror("Compte invalide", f"Le compte créditeur « {data['compte_credit']} » "
                                                      f"n'existe pas dans le Plan comptable. Créez-le d'abord "
                                                      f"(quittez le champ pour être invité à le créer).")
            return
        try:
            core.add_balanced_entry(
                self.conn, data["date_str"], data["piece"], data["journal"],
                data["compte_debit"], data["compte_credit"], data["montant"],
                data["tiers"], data["libelle"],
                analytic_code=data["analytic_code"], budget_code=data["budget_code"],
                donor_code=data["donor_code"], quantite=data["quantite"],
                fournisseur_code=data["fournisseur_code"],
            )
        except ValueError as exc:
            messagebox.showerror("Erreur", str(exc))
            return
        self.refresh()
        self.balance_var.set("")
        piece = self.vars["N° Pièce"].get().strip()
        for k in ("Compte débiteur", "Compte créditeur", "Montant", "Tiers", "Libellé", "Fournisseur",
                  "Code analytique (ex: AN-FAB)", "Code budgétaire", "Code bailleur", "Quantité"):
            self.vars[k].set("")
        self.vars["N° Pièce"].set(piece)  # facilite l'ajout d'autres paires sur la même pièce
        self.account_label_var.set("")
        self.selected_id = None
        self.compte_debit_combo.focus_set()

    def update_entry(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne dans le tableau.")
            return
        debit_code = self._extract_code(self.vars["Compte débiteur"].get())
        credit_code = self._extract_code(self.vars["Compte créditeur"].get())
        if debit_code and credit_code:
            messagebox.showwarning(
                "Une seule ligne à la fois",
                "Pour modifier une écriture existante, ne renseignez que le compte du côté "
                "concerné (Débit OU Crédit), pas les deux — chaque ligne du tableau est une "
                "moitié d'une écriture en partie double."
            )
            return
        try:
            montant = float(self.vars["Montant"].get() or 0)
            quantite = float(self.vars["Quantité"].get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Montant et Quantité doivent être des nombres.")
            return
        if debit_code:
            if not core.account_exists(self.conn, debit_code):
                messagebox.showerror("Compte invalide", f"Le compte « {debit_code} » n'existe pas.")
                return
            fields = dict(compte=debit_code, debit=montant, credit=0)
        elif credit_code:
            if not core.account_exists(self.conn, credit_code):
                messagebox.showerror("Compte invalide", f"Le compte « {credit_code} » n'existe pas.")
                return
            fields = dict(compte=credit_code, debit=0, credit=montant)
        else:
            messagebox.showwarning("Champ manquant", "Renseignez le compte (débiteur ou créditeur) de cette ligne.")
            return
        fields.update(
            date=core.to_iso_date(self.vars["Date (JJ/MM/AAAA)"].get().strip()),
            piece=self.vars["N° Pièce"].get().strip(),
            journal=self.vars["Journal"].get().strip(),
            tiers=self.vars["Tiers"].get().strip(),
            libelle=self.vars["Libellé"].get().strip(),
            analytic_code=self._extract_code(self.vars["Code analytique (ex: AN-FAB)"].get()),
            budget_code=self._extract_code(self.vars["Code budgétaire"].get()),
            donor_code=self._extract_code(self.vars["Code bailleur"].get()),
            fournisseur_code=self._extract_code(self.vars["Fournisseur"].get()),
            quantite=quantite,
        )
        try:
            core.update_entry(self.conn, self.selected_id, **fields)
        except ValueError as exc:
            messagebox.showerror("Erreur", str(exc))
            return
        self.clear_form()
        self.refresh()

    def delete_entry(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne dans le tableau.")
            return
        if messagebox.askyesno("Confirmer", "Supprimer cette écriture ?"):
            try:
                core.delete_entry(self.conn, self.selected_id)
            except ValueError as exc:
                messagebox.showerror("Erreur", str(exc))
                return
            self.clear_form()
            self.refresh()

    def clear_form(self):
        self.selected_id = None
        self.pending_piece = None
        self.balance_var.set("")
        for k, v in self.vars.items():
            v.set("" if k != "Date (JJ/MM/AAAA)" else self._default_date())
        self.account_label_var.set("")

    def download_template(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile="Modele_import_ecritures.xlsx",
            title="Enregistrer le modèle d'import",
        )
        if not path:
            return
        try:
            core.export_import_template(path)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec de la création du modèle : {exc}")
            return
        messagebox.showinfo("Modèle créé", f"Modèle enregistré :\n{path}")

    def import_xlsx(self):
        path = filedialog.askopenfilename(
            filetypes=[("Classeur Excel", "*.xlsx")],
            title="Importer des écritures",
        )
        if not path:
            return
        try:
            imported, warnings = core.import_entries_from_xlsx(self.conn, path)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec de l'import : {exc}")
            return
        self.refresh()
        if warnings:
            preview = "\n".join(warnings[:25])
            more = f"\n... et {len(warnings) - 25} autre(s)." if len(warnings) > 25 else ""
            messagebox.showwarning(
                "Import terminé avec avertissements",
                f"{imported} écriture(s) importée(s).\n\nAvertissements :\n{preview}{more}",
            )
        else:
            messagebox.showinfo("Import terminé", f"{imported} écriture(s) importée(s) avec succès.")

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.selected_id = int(values[0])
        self.vars["Date (JJ/MM/AAAA)"].set(values[1])
        self.vars["N° Pièce"].set(values[2])
        self.vars["Journal"].set(values[3])
        compte = values[4]
        debit_val = values[8]
        credit_val = values[9]
        self.vars["Compte débiteur"].set("")
        self.vars["Compte créditeur"].set("")
        if debit_val:
            self.vars["Compte débiteur"].set(compte)
            self.vars["Montant"].set(debit_val)
        else:
            self.vars["Compte créditeur"].set(compte)
            self.vars["Montant"].set(credit_val)
        self.vars["Tiers"].set(values[6])
        self.vars["Libellé"].set(values[7])
        self.vars["Quantité"].set(values[10])
        self.vars["Code analytique (ex: AN-FAB)"].set(values[11])
        self.vars["Code budgétaire"].set(values[12])
        self.vars["Code bailleur"].set(values[13])
        self.vars["Fournisseur"].set(values[14])
        self._show_account_labels()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        entries = core.list_entries(self.conn, exercice=core.get_current_exercice(self.conn))
        total_d = total_c = 0.0
        for e in entries:
            label = core.get_account_label(self.conn, e["compte"])
            self.tree.insert("", "end", values=(
                e["id"], core.to_display_date(e["date"]), e["piece"] or "", e["journal"] or "", e["compte"], label,
                e["tiers"] or "", e["libelle"] or "",
                f"{e['debit']:.2f}" if e["debit"] else "",
                f"{e['credit']:.2f}" if e["credit"] else "",
                f"{e['quantite']:g}" if e["quantite"] else "",
                e["analytic_code"] or "",
                e["budget_code"] or "",
                e["donor_code"] or "",
                e["fournisseur_code"] or "",
            ))
            total_d += e["debit"]
            total_c += e["credit"]
        equilibre = "Équilibré ✓" if abs(total_d - total_c) < 0.01 else "NON ÉQUILIBRÉ ✗"
        self.totals_var.set(f"TOTAUX — Débit : {total_d:,.2f}   Crédit : {total_c:,.2f}   {equilibre}")


class BalanceTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        cols = ("compte", "libelle", "ouverture", "debit", "credit", "mouvement", "cloture")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé du compte", "Solde Ouverture", "Total Débit", "Total Crédit",
                   "Solde Mouvement", "Solde Clôture"]
        widths = [90, 280, 110, 100, 100, 110, 110]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(pady=(0, 8))
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for b in core.compute_balance(self.conn):
            self.tree.insert("", "end", values=(
                b["code"], b["label"], f"{b['solde_ouverture']:,.2f}",
                f"{b['debit']:,.2f}", f"{b['credit']:,.2f}",
                f"{b['solde']:,.2f}", f"{b['solde_cloture']:,.2f}"
            ))


class CompteResultatTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(pady=(0, 8))
        self.refresh()

    def refresh(self):
        cr = core.compute_compte_resultat(self.conn)
        lines = ["COMPTE DE RÉSULTAT", "=" * 60, "", "PRODUITS D'EXPLOITATION"]
        for k, v in cr["produits"].items():
            lines.append(f"  {k:<50} {v:>12,.2f}")
        lines.append(f"  {'TOTAL PRODUITS':<50} {cr['total_produits']:>12,.2f}")
        lines += ["", "CHARGES D'EXPLOITATION"]
        for k, v in cr["charges"].items():
            lines.append(f"  {k:<50} {v:>12,.2f}")
        lines.append(f"  {'TOTAL CHARGES':<50} {cr['total_charges']:>12,.2f}")
        lines += ["", f"RÉSULTAT D'EXPLOITATION{'':<39}{cr['resultat_exploitation']:>12,.2f}", ""]
        lines += ["RÉSULTAT FINANCIER",
                  f"  Produits financiers{'':<38}{cr['produits_financiers']:>12,.2f}",
                  f"  Charges financières{'':<38}{cr['charges_financieres']:>12,.2f}",
                  f"  {'RÉSULTAT FINANCIER':<50} {cr['resultat_financier']:>12,.2f}", ""]
        label_rn = "RÉSULTAT NET DE L'EXERCICE"
        lines.append(f"{label_rn:<52} {cr['resultat_net']:>12,.2f}")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class BilanTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(pady=(0, 8))
        self.refresh()

    def refresh(self):
        b = core.compute_bilan(self.conn)
        lines = ["BILAN", "=" * 60, "", "ACTIF"]
        for k, v in b["actif"].items():
            lines.append(f"  {k:<50} {v:>12,.2f}")
        lines.append(f"  {'TOTAL ACTIF':<50} {b['total_actif']:>12,.2f}")
        lines += ["", "PASSIF"]
        for k, v in b["passif"].items():
            lines.append(f"  {k:<50} {v:>12,.2f}")
        lines.append(f"  {'TOTAL PASSIF':<50} {b['total_passif']:>12,.2f}")
        lines += ["", f"Écart Actif - Passif : {b['ecart']:,.2f}",
                  "(doit être proche de 0 ; un écart signale des soldes d'ouverture non saisis)"]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class GrandLivreTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="N° Compte :").pack(side="left")
        self.compte_var = tk.StringVar()
        self.compte_combo = ttk.Combobox(bar, textvariable=self.compte_var, width=30)
        self.compte_combo.pack(side="left", padx=4)
        self.compte_combo.bind("<KeyRelease>", self._on_compte_keyrelease)
        self.compte_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="Tiers (optionnel) :").pack(side="left", padx=(12, 0))
        self.tiers_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.tiers_var, width=18).pack(side="left", padx=4)
        ttk.Button(bar, text="Afficher", command=self.refresh).pack(side="left", padx=12)
        self.label_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.label_var, foreground="#1F4E78").pack(side="left", padx=8)

        cols = ("date", "piece", "journal", "tiers", "libelle", "debit", "credit", "solde")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["Date", "Pièce", "Journal", "Tiers", "Libellé", "Débit", "Crédit", "Solde cumulé"]
        widths = [90, 80, 60, 140, 260, 90, 90, 100]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _extract_compte_code(self):
        raw = self.compte_var.get().strip()
        if " — " in raw:
            return raw.split(" — ", 1)[0].strip()
        return raw

    def _on_compte_keyrelease(self, event=None):
        if event is not None and event.keysym in ("Up", "Down", "Return", "Tab"):
            return
        query = self._extract_compte_code()
        if query:
            matches = core.search_accounts(self.conn, query, limit=30)
            self.compte_combo["values"] = [f"{m['code']} — {m['label']}" for m in matches]

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        compte = self._extract_compte_code()
        if not compte:
            self.label_var.set("")
            return
        self.label_var.set(core.get_account_label(self.conn, compte))
        for r in core.compute_grand_livre(self.conn, compte, self.tiers_var.get().strip() or None):
            self.tree.insert("", "end", values=(
                core.to_display_date(r["date"]), r["piece"] or "", r["journal"] or "", r["tiers"] or "", r["libelle"] or "",
                f"{r['debit']:.2f}" if r["debit"] else "",
                f"{r['credit']:.2f}" if r["credit"] else "",
                f"{r['solde_cumule']:,.2f}",
            ))


class OpeningBalancesTab(ttk.Frame):
    """Soldes d'ouverture (report à nouveau) : un solde signé par compte, saisi
    une fois en début d'exercice. Débiteur = positif, créditeur = négatif."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn

        ttk.Label(self, text=(
            "Saisissez ici le solde de report à nouveau de chaque compte de bilan au 1er jour de "
            "l'exercice (= solde de clôture de l'exercice précédent). Convention : solde débiteur = "
            "positif, solde créditeur = négatif (ex. Capital social créditeur de 5 000 000 → -5000000). "
            "La « Balance de clôture » (onglet Balance) et le Bilan intègrent automatiquement ces soldes."
        ), foreground="#595959", wraplength=1000).pack(anchor="w", padx=8, pady=(8, 4))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=8, pady=4)
        ttk.Label(form, text="N° Compte :").pack(side="left")
        self.compte_var = tk.StringVar()
        self.compte_combo = ttk.Combobox(form, textvariable=self.compte_var, width=34)
        self.compte_combo.pack(side="left", padx=4)
        self.compte_combo.bind("<KeyRelease>", self._on_compte_keyrelease)
        ttk.Label(form, text="Solde d'ouverture :").pack(side="left", padx=(12, 0))
        self.solde_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.solde_var, width=16).pack(side="left", padx=4)
        ttk.Button(form, text="Enregistrer", command=self.save).pack(side="left", padx=6)

        cols = ("code", "label", "solde")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé", "Solde d'ouverture"]
        widths = [90, 400, 140]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        self.total_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.total_var, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.refresh()

    def _extract_compte_code(self):
        raw = self.compte_var.get().strip()
        if " — " in raw:
            return raw.split(" — ", 1)[0].strip()
        return raw

    def _on_compte_keyrelease(self, event=None):
        if event is not None and event.keysym in ("Up", "Down", "Return", "Tab"):
            return
        query = self._extract_compte_code()
        if query:
            matches = core.search_accounts(self.conn, query, limit=30)
            self.compte_combo["values"] = [f"{m['code']} — {m['label']}" for m in matches]

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.compte_var.set(values[0])
        self.solde_var.set(values[2])

    def save(self):
        code = self._extract_compte_code()
        if not code:
            messagebox.showinfo("Info", "Choisissez d'abord un compte.")
            return
        try:
            value = float(self.solde_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le solde d'ouverture doit être un nombre.")
            return
        core.set_opening_balance(self.conn, code, value)
        self.compte_var.set("")
        self.solde_var.set("")
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        total = 0.0
        for b in core.list_opening_balances(self.conn):
            self.tree.insert("", "end", values=(b["code"], b["label"], f"{b['solde']:,.2f}"))
            total += b["solde"]
        equilibre = "Équilibré ✓" if abs(total) < 0.01 else "NON ÉQUILIBRÉ ✗ (la somme des soldes d'ouverture doit être nulle)"
        self.total_var.set(f"Somme des soldes d'ouverture : {total:,.2f}   {equilibre}")


class StocksTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text=(
            "Stock initial (valeur ou quantité) : cliquez une ligne, modifiez la valeur puis "
            "« Enregistrer ». La quantité de mouvement provient du champ « Quantité » saisi sur "
            "chaque écriture (onglet Saisie) — elle permet de calculer un coût unitaire moyen pour "
            "la valorisation des stocks."
        ), foreground="#595959", wraplength=1000).pack(anchor="w", padx=8, pady=(8, 0))

        edit_bar = ttk.Frame(self)
        edit_bar.pack(fill="x", padx=8, pady=4)
        ttk.Label(edit_bar, text="Stock initial (valeur) du compte sélectionné :").pack(side="left")
        self.initial_var = tk.StringVar()
        ttk.Entry(edit_bar, textvariable=self.initial_var, width=14).pack(side="left", padx=4)
        ttk.Button(edit_bar, text="Enregistrer la valeur", command=self.save_initial).pack(side="left", padx=4)
        ttk.Label(edit_bar, text="Quantité initiale :").pack(side="left", padx=(16, 0))
        self.qte_initial_var = tk.StringVar()
        ttk.Entry(edit_bar, textvariable=self.qte_initial_var, width=14).pack(side="left", padx=4)
        ttk.Button(edit_bar, text="Enregistrer la quantité", command=self.save_qte_initial).pack(side="left", padx=4)

        cols = ("code", "label", "initial", "entrees", "sorties", "final",
                "qte_initiale", "qte_entrees", "qte_sorties", "qte_finale", "cump")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé", "Stock initial", "Entrées (Débit)", "Sorties (Crédit)", "Stock final",
                   "Qté initiale", "Qté entrées", "Qté sorties", "Qté finale", "Coût unit. moyen"]
        widths = [90, 190, 100, 100, 100, 100, 80, 80, 80, 80, 110]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.selected_code = None
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.selected_code = values[0]
        self.initial_var.set(values[2])
        self.qte_initial_var.set(values[6])

    def save_initial(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un compte de stock dans le tableau.")
            return
        try:
            value = float(self.initial_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le stock initial doit être un nombre.")
            return
        core.set_stock_initial(self.conn, self.selected_code, value)
        self.refresh()

    def save_qte_initial(self):
        if not self.selected_code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un compte de stock dans le tableau.")
            return
        try:
            value = float(self.qte_initial_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "La quantité initiale doit être un nombre.")
            return
        core.set_stock_qte_initiale(self.conn, self.selected_code, value)
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in core.compute_stocks(self.conn):
            cump = f"{s['cout_unitaire_moyen']:,.2f}" if s["cout_unitaire_moyen"] is not None else "—"
            self.tree.insert("", "end", values=(
                s["code"], s["label"], f"{s['stock_initial']:,.2f}",
                f"{s['entrees']:,.2f}", f"{s['sorties']:,.2f}", f"{s['stock_final']:,.2f}",
                f"{s['qte_initiale']:g}", f"{s['qte_entrees']:g}", f"{s['qte_sorties']:g}",
                f"{s['qte_finale']:g}", cump,
            ))


class ProductionTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text=(
            "Pour qu'une charge remonte ici, saisissez le code analytique « AN-FAB » "
            "sur la ligne correspondante dans l'onglet Saisie."
        ), foreground="#595959").pack(anchor="w", padx=8, pady=(8, 0))
        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Actualiser", command=self.refresh).pack(pady=(0, 8))
        self.refresh()

    def refresh(self):
        p = core.compute_production(self.conn)
        lines = ["PRODUCTION DE L'EXERCICE", "=" * 60,
                 f"  {'Ventes (produits finis, travaux, services)':<50} {p['ventes']:>12,.2f}",
                 f"  {'Production stockée (variation stock 360000)':<50} {p['production_stockee']:>12,.2f}",
                 f"  {'VALEUR DE LA PRODUCTION':<50} {p['valeur_production']:>12,.2f}",
                 "", "COÛTS DE FABRICATION (axe AN-FAB)", "=" * 60]
        for poste in p["postes_cout"]:
            lines.append(f"  {poste['label']:<50} {poste['montant']:>12,.2f}")
        lines += [f"  {'COÛT DE PRODUCTION':<50} {p['cout_production']:>12,.2f}", "",
                  f"MARGE SUR COÛT DE PRODUCTION{'':<34}{p['marge']:>12,.2f}"]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class TftTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Trésorerie d'ouverture (auto., ou forcez une valeur) :").pack(side="left")
        self.ouverture_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.ouverture_var, width=14).pack(side="left", padx=4)
        ttk.Button(bar, text="Forcer cette valeur", command=self.save_and_refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Revenir à l'automatique", command=self.reset_auto).pack(side="left", padx=4)
        ttk.Label(bar, text=(
            "Par défaut = somme des soldes d'ouverture des comptes de trésorerie (onglet « Soldes "
            "d'ouverture »). Les mouvements se classent par nature via le code flux EXP/INV/FIN saisi "
            "dans l'onglet Saisie."
        ), foreground="#595959", wraplength=550).pack(side="left", padx=12)

        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def save_and_refresh(self):
        try:
            value = float(self.ouverture_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "La trésorerie d'ouverture doit être un nombre.")
            return
        core.set_setting(self.conn, "treso_ouverture_override", value)
        core.set_setting(self.conn, "treso_ouverture_use_override", 1)
        self.refresh()

    def reset_auto(self):
        core.set_setting(self.conn, "treso_ouverture_use_override", 0)
        self.refresh()

    def refresh(self):
        use_override = core.get_setting(self.conn, "treso_ouverture_use_override", 0.0)
        ouverture_override = core.get_setting(self.conn, "treso_ouverture_override", 0.0) if use_override else None
        t = core.compute_tft(self.conn, treso_ouverture=ouverture_override)
        self.ouverture_var.set(str(t["ouverture"]))
        label_ouv = "Trésorerie d'ouverture"
        label_inv = "Flux liés aux activités d'investissement (INV)"
        label_clot = "TRÉSORERIE DE CLÔTURE"
        lines = [
            "TABLEAU DES FLUX DE TRÉSORERIE (méthode directe)", "=" * 60,
            f"  {label_ouv:<50} {t['ouverture']:>12,.2f}", "",
            f"  {'Flux liés aux activités opérationnelles (EXP)':<50} {t['exploitation']:>12,.2f}",
            f"  {label_inv:<50} {t['investissement']:>12,.2f}",
            f"  {'Flux liés aux activités de financement (FIN)':<50} {t['financement']:>12,.2f}",
            f"  {'Flux non classés (à coder)':<50} {t['non_classes']:>12,.2f}",
            f"  {'VARIATION NETTE DE TRÉSORERIE':<50} {t['variation']:>12,.2f}", "",
            f"{label_clot:<52} {t['cloture']:>12,.2f}",
        ]
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class LiasseFiscaleTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn

        info = ttk.LabelFrame(self, text="Identification de l'entité (SYSCOHADA / DGI)")
        info.pack(fill="x", padx=8, pady=8)

        self.vars = {}
        for i, (key, label) in enumerate(core.COMPANY_FIELDS.items()):
            r, c = divmod(i, 2)
            ttk.Label(info, text=label + " :").grid(row=r * 2, column=c, sticky="w", padx=4, pady=(4, 0))
            var = tk.StringVar(value=core.get_company_value(conn, key))
            ttk.Entry(info, textvariable=var, width=40).grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 6))
            self.vars[key] = var
        ttk.Button(info, text="Enregistrer les informations", command=self.save_info).grid(
            row=6, column=0, sticky="w", padx=4, pady=6)

        params = ttk.LabelFrame(self, text="Paramètres d'export")
        params.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(params, text="Stock initial total (cf. onglet Stocks) :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.stock_initial_var = tk.StringVar(value="0")
        ttk.Entry(params, textvariable=self.stock_initial_var, width=16).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(params, text="(complément optionnel — utilisez plutôt l'onglet « Soldes d'ouverture »)",
                  foreground="#595959").grid(row=0, column=2, sticky="w", padx=(10, 4))

        note = ttk.Label(self, wraplength=900, foreground="#595959", text=(
            "Génère un classeur .xlsx COMPLET reprenant les 92 pages du modèle SYSCOHADA système "
            "normal (mêmes dimensions, mêmes codes officiels) : COUVERTURE, BILAN, RESULTAT, TFT, "
            "39 notes annexes, ~20 tableaux fiscaux DGI. BILAN et RESULTAT sont calculés automatiquement "
            "depuis vos écritures (soldes de clôture = solde d'ouverture + mouvements de l'exercice, "
            "cf. onglet « Soldes d'ouverture »). Le TFT officiel (méthode indirecte, CAFG) est laissé "
            "vierge — un onglet « TFT (simplifie) » calculé en méthode directe est ajouté à titre "
            "indicatif. Toutes les autres pages gardent leur mise en page et leurs dimensions exactes, "
            "mais leurs valeurs sont vidées (ce ne sont pas vos chiffres) pour être complétées "
            "manuellement — le détail des lignes du Bilan (AE à AN, CA à CM, DA à DM) est une "
            "répartition indicative par plage de comptes. À faire vérifier par un expert-comptable "
            "avant tout dépôt officiel auprès de la DGI."
        ))
        note.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(self, text="Exporter la liasse fiscale complète (.xlsx)", command=self.export).pack(padx=8, pady=8, anchor="w")
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground="#1F4E78").pack(padx=8, anchor="w")

    def save_info(self):
        for key, var in self.vars.items():
            core.set_company_value(self.conn, key, var.get().strip())
        self.status_var.set("Informations enregistrées.")

    def export(self):
        self.save_info()
        try:
            stock_initial = float(self.stock_initial_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le complément de stock initial doit être un nombre.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile="Liasse_fiscale.xlsx",
            title="Enregistrer la liasse fiscale",
        )
        if not path:
            return
        try:
            core.export_liasse_fiscale_complete(self.conn, path, stock_initial=stock_initial)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec de l'export : {exc}")
            return
        self.status_var.set(f"Export réussi : {path}")
        messagebox.showinfo("Export terminé", f"Liasse fiscale enregistrée :\n{path}")


class PlaceholderTab(ttk.Frame):
    """Page pas encore développée : structure de menu en place, contenu à venir."""

    def __init__(self, parent, conn, title, description):
        super().__init__(parent)
        ttk.Label(self, text=title, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=24, pady=(24, 8))
        ttk.Label(self, text=description, wraplength=900, foreground="#595959").pack(anchor="w", padx=24)
        ttk.Label(self, text="Fonctionnalité pas encore développée — dites-moi si vous voulez que je "
                              "la construise en priorité.", foreground="#B00020").pack(anchor="w", padx=24, pady=(16, 0))


class VentesTab(ttk.Frame):
    """Synthèse des comptes de vente (classe 7, hors produits financiers)."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="VENTES", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        cols = ("code", "label", "debit", "credit", "net")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé", "Débit", "Crédit", "Ventes nettes (Crédit - Débit)"]
        widths = [90, 320, 110, 110, 150]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.total_var = tk.StringVar()
        ttk.Label(self, textvariable=self.total_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(0, 12))
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        total = 0.0
        for b in core.compute_balance(self.conn, only_with_movement=False):
            if b["classe"] != "7" or int(b["code"]) in (771000, 776000):
                continue
            net = b["credit"] - b["debit"]
            if b["debit"] == 0 and b["credit"] == 0:
                continue
            self.tree.insert("", "end", values=(b["code"], b["label"], f"{b['debit']:,.2f}",
                                                 f"{b['credit']:,.2f}", f"{net:,.2f}"))
            total += net
        self.total_var.set(f"TOTAL VENTES NETTES : {total:,.2f}")


class AchatsTab(ttk.Frame):
    """Soldes des opérations avec chaque fournisseur, total par fournisseur,
    avec filtre sur une plage de dates."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="ACHATS — SOLDES PAR FOURNISSEUR", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        ttk.Label(self, text=(
            "Solde = Débit − Crédit sur les comptes fournisseurs (401xxx/408xxx) taggés à chaque "
            "fournisseur dans la Saisie. Négatif = montant restant dû au fournisseur."
        ), foreground="#595959", wraplength=1000).pack(anchor="w", padx=16, pady=(0, 8))

        filt = ttk.Frame(self)
        filt.pack(fill="x", padx=16, pady=4)
        ttk.Label(filt, text="Du (JJ/MM/AAAA) :").pack(side="left")
        self.date_from_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self.date_from_var, width=12).pack(side="left", padx=4)
        ttk.Label(filt, text="Au (JJ/MM/AAAA) :").pack(side="left", padx=(12, 0))
        self.date_to_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self.date_to_var, width=12).pack(side="left", padx=4)
        ttk.Button(filt, text="Filtrer", command=self.refresh).pack(side="left", padx=8)
        ttk.Button(filt, text="Réinitialiser", command=self._reset_filter).pack(side="left", padx=2)

        cols = ("code", "raison_sociale", "debit", "credit", "solde")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["Code", "Fournisseur", "Total Débit", "Total Crédit", "Solde (dû si négatif)"]
        widths = [90, 320, 120, 120, 160]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.total_var = tk.StringVar()
        ttk.Label(self, textvariable=self.total_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(0, 12))
        self.refresh()

    def _reset_filter(self):
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        date_from = core.to_iso_date(self.date_from_var.get()) if self.date_from_var.get().strip() else None
        date_to = core.to_iso_date(self.date_to_var.get()) if self.date_to_var.get().strip() else None
        achats, total_debit, total_credit = core.compute_achats_par_fournisseur(
            self.conn, date_from=date_from, date_to=date_to)
        for a in achats:
            self.tree.insert("", "end", values=(
                a["code"], a["raison_sociale"], f"{a['debit']:,.2f}", f"{a['credit']:,.2f}", f"{a['solde']:,.2f}"
            ))
        self.total_var.set(
            f"TOTAL — Débit : {total_debit:,.2f}   Crédit : {total_credit:,.2f}   "
            f"Solde global : {total_debit - total_credit:,.2f}"
        )


class MargesTab(ttk.Frame):
    """Marge commerciale et valeur ajoutée, calculées comme dans la Liasse fiscale."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=16, pady=16)
        self.refresh()

    def refresh(self):
        cr = core.compute_liasse_resultat(self.conn)
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


class ClientsTab(GrandLivreTab):
    """Grand livre pré-filtré sur le compte Clients (411000)."""

    def __init__(self, parent, conn):
        super().__init__(parent, conn)
        self.compte_var.set("411000")
        self.refresh()


class FournisseursTab(ttk.Frame):
    """Liste auxiliaire des fournisseurs : créer / modifier / importer."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="FOURNISSEURS (LISTE AUXILIAIRE)", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16, pady=4)
        labels = ["Code", "Raison sociale", "Contact", "Téléphone", "Adresse",
                  "Délai paiement (jours)", "Délai livraison (jours)"]
        self.vars = {k: tk.StringVar() for k in labels}
        for i, lbl in enumerate(labels):
            r, c = divmod(i, 4)
            ttk.Label(form, text=lbl + " :").grid(row=r * 2, column=c, sticky="w", padx=4, pady=(4, 0))
            ttk.Entry(form, textvariable=self.vars[lbl], width=22).grid(
                row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
        btns = ttk.Frame(form)
        btns.grid(row=4, column=0, columnspan=4, sticky="w", pady=6)
        ttk.Button(btns, text="Créer / Modifier", command=self.save).pack(side="left", padx=2)
        ttk.Button(btns, text="Supprimer", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=2)

        import_bar = ttk.Frame(self)
        import_bar.pack(fill="x", padx=16, pady=(4, 4))
        ttk.Button(import_bar, text="Importer des fournisseurs (.xlsx)", command=self.import_xlsx).pack(side="left", padx=2)
        ttk.Button(import_bar, text="Télécharger un modèle (.xlsx)", command=self.download_template).pack(side="left", padx=2)

        search_bar = ttk.Frame(self)
        search_bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(search_bar, text="Rechercher :").pack(side="left")
        self.search_var = tk.StringVar()
        se = ttk.Entry(search_bar, textvariable=self.search_var, width=30)
        se.pack(side="left", padx=6)
        se.bind("<KeyRelease>", lambda e: self.refresh())

        cols = ("code", "raison_sociale", "contact", "telephone", "adresse", "dp", "dl")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["Code", "Raison sociale", "Contact", "Téléphone", "Adresse",
                   "Délai paiement (j)", "Délai livraison (j)"]
        widths = [90, 220, 130, 110, 200, 110, 110]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.vars["Code"].set(v[0])
        self.vars["Raison sociale"].set(v[1])
        self.vars["Contact"].set(v[2])
        self.vars["Téléphone"].set(v[3])
        self.vars["Adresse"].set(v[4])
        self.vars["Délai paiement (jours)"].set(v[5])
        self.vars["Délai livraison (jours)"].set(v[6])

    def clear_form(self):
        for v in self.vars.values():
            v.set("")

    def save(self):
        code = self.vars["Code"].get().strip()
        raison = self.vars["Raison sociale"].get().strip()
        if not code or not raison:
            messagebox.showwarning("Champs manquants", "Code et Raison sociale sont obligatoires.")
            return
        try:
            dp = int(self.vars["Délai paiement (jours)"].get() or 30)
            dl = int(self.vars["Délai livraison (jours)"].get() or 15)
        except ValueError:
            messagebox.showerror("Erreur", "Les délais doivent être des nombres entiers de jours.")
            return
        core.add_fournisseur(self.conn, code, raison, self.vars["Contact"].get().strip(),
                              self.vars["Téléphone"].get().strip(), self.vars["Adresse"].get().strip(),
                              dp, dl)
        self.refresh()

    def delete(self):
        code = self.vars["Code"].get().strip()
        if not code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un fournisseur.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer le fournisseur {code} ?"):
            core.delete_fournisseur(self.conn, code)
            self.clear_form()
            self.refresh()

    def download_template(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile="Modele_fournisseurs.xlsx", title="Enregistrer le modèle",
        )
        if not path:
            return
        core.export_fournisseurs_template(path)
        messagebox.showinfo("Modèle créé", f"Modèle enregistré :\n{path}")

    def import_xlsx(self):
        path = filedialog.askopenfilename(filetypes=[("Classeur Excel", "*.xlsx")],
                                           title="Importer des fournisseurs")
        if not path:
            return
        try:
            imported, warnings = core.import_fournisseurs_from_xlsx(self.conn, path)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Échec de l'import : {exc}")
            return
        self.refresh()
        msg = f"{imported} fournisseur(s) importé(s)."
        if warnings:
            msg += "\n\nAvertissements :\n" + "\n".join(warnings[:20])
        messagebox.showinfo("Import terminé", msg)

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for f in core.list_fournisseurs(self.conn, self.search_var.get().strip() or None):
            self.tree.insert("", "end", values=(
                f["code"], f["raison_sociale"], f["contact"] or "", f["telephone"] or "",
                f["adresse"] or "", f["delai_paiement_jours"], f["delai_livraison_jours"],
            ))


class ContratsTab(ttk.Frame):
    """Journal des commandes/contrats fournisseurs : délais de paiement et de
    livraison, avec détection des dépassements."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="CONTRATS FOURNISSEURS — SUIVI DES DÉLAIS",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Label(self, text=(
            "Enregistrez ici chaque commande/contrat passé avec un fournisseur. Les échéances de "
            "livraison et de paiement sont calculées automatiquement à partir des délais par défaut "
            "du fournisseur (modifiables dans l'onglet Fournisseurs), à la date de commande. "
            "Renseignez ensuite les dates réelles de livraison/paiement au fur et à mesure — les "
            "dépassements sont signalés automatiquement."
        ), foreground="#595959", wraplength=1050).pack(anchor="w", padx=16, pady=(0, 8))

        form = ttk.LabelFrame(self, text="Nouvelle commande / contrat")
        form.pack(fill="x", padx=16, pady=4)
        ttk.Label(form, text="Fournisseur :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.fournisseur_var = tk.StringVar()
        self.fournisseur_combo = ttk.Combobox(form, textvariable=self.fournisseur_var, width=28)
        self.fournisseur_combo.grid(row=0, column=1, padx=4)
        self.fournisseur_combo.bind("<KeyRelease>", self._on_fournisseur_keyrelease)
        self._refresh_fournisseur_values()

        ttk.Label(form, text="N° Pièce :").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self.piece_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.piece_var, width=14).grid(row=0, column=3, padx=4)

        ttk.Label(form, text="Libellé :").grid(row=0, column=4, sticky="w", padx=(12, 4))
        self.libelle_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.libelle_var, width=26).grid(row=0, column=5, padx=4)

        ttk.Label(form, text="Montant :").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.montant_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.montant_var, width=16).grid(row=1, column=1, padx=4)

        ttk.Label(form, text="Date commande (JJ/MM/AAAA) :").grid(row=1, column=2, sticky="w", padx=(12, 4))
        self.date_commande_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(form, textvariable=self.date_commande_var, width=14).grid(row=1, column=3, padx=4)

        ttk.Button(form, text="Créer la commande (échéances auto)", command=self.add_commande).grid(
            row=1, column=4, columnspan=2, sticky="w", padx=12, pady=4)

        update_frame = ttk.LabelFrame(self, text="Mettre à jour la commande sélectionnée (dates réelles)")
        update_frame.pack(fill="x", padx=16, pady=(8, 4))
        ttk.Label(update_frame, text="Date livraison réelle (JJ/MM/AAAA) :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.livraison_reelle_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.livraison_reelle_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Button(update_frame, text="Enregistrer la livraison", command=self.save_livraison).grid(
            row=0, column=2, padx=8)
        ttk.Label(update_frame, text="Date paiement réel (JJ/MM/AAAA) :").grid(row=0, column=3, sticky="w", padx=(20, 4))
        self.paiement_reel_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.paiement_reel_var, width=14).grid(row=0, column=4, padx=4)
        ttk.Button(update_frame, text="Enregistrer le paiement", command=self.save_paiement).grid(
            row=0, column=5, padx=8)
        ttk.Button(update_frame, text="Supprimer la commande sélectionnée", command=self.delete_commande).grid(
            row=0, column=6, padx=20)

        cols = ("id", "fournisseur", "piece", "libelle", "montant", "date_commande",
                "livraison_prevue", "statut_livraison", "echeance_paiement", "statut_paiement")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["ID", "Fournisseur", "Pièce", "Libellé", "Montant", "Date commande",
                   "Livraison prévue", "Statut livraison", "Échéance paiement", "Statut paiement"]
        widths = [40, 160, 80, 160, 100, 100, 100, 140, 110, 140]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("depasse", foreground="#B00020")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.selected_id = None
        self.refresh()

    def _refresh_fournisseur_values(self):
        items = core.list_fournisseurs(self.conn)
        self.fournisseur_combo["values"] = [f"{f['code']} — {f['raison_sociale']}" for f in items]

    def _on_fournisseur_keyrelease(self, event=None):
        query = self._extract_code(self.fournisseur_var.get())
        if query:
            items = core.list_fournisseurs(self.conn, query)
            self.fournisseur_combo["values"] = [f"{f['code']} — {f['raison_sociale']}" for f in items]

    @staticmethod
    def _extract_code(raw):
        raw = (raw or "").strip()
        return raw.split(" — ", 1)[0].strip() if " — " in raw else raw

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.selected_id = int(values[0])

    def add_commande(self):
        code = self._extract_code(self.fournisseur_var.get())
        if not code:
            messagebox.showwarning("Champ manquant", "Choisissez un fournisseur.")
            return
        if not core.fournisseur_exists(self.conn, code):
            messagebox.showerror("Fournisseur invalide", f"Le fournisseur « {code} » n'existe pas. "
                                                           f"Créez-le d'abord dans l'onglet Fournisseurs.")
            return
        try:
            montant = float(self.montant_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le montant doit être un nombre.")
            return
        date_commande = core.to_iso_date(self.date_commande_var.get().strip())
        if not date_commande:
            messagebox.showwarning("Champ manquant", "La date de commande est obligatoire.")
            return
        core.add_commande(self.conn, code, self.piece_var.get().strip(), self.libelle_var.get().strip(),
                           montant, date_commande)
        self.piece_var.set("")
        self.libelle_var.set("")
        self.montant_var.set("")
        self.refresh()

    def save_livraison(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une commande dans le tableau.")
            return
        d = core.to_iso_date(self.livraison_reelle_var.get().strip())
        if not d:
            messagebox.showwarning("Champ manquant", "Saisissez la date de livraison réelle.")
            return
        core.update_commande(self.conn, self.selected_id, date_livraison_reelle=d)
        self.livraison_reelle_var.set("")
        self.refresh()

    def save_paiement(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une commande dans le tableau.")
            return
        d = core.to_iso_date(self.paiement_reel_var.get().strip())
        if not d:
            messagebox.showwarning("Champ manquant", "Saisissez la date de paiement réel.")
            return
        core.update_commande(self.conn, self.selected_id, date_paiement_reel=d)
        self.paiement_reel_var.set("")
        self.refresh()

    def delete_commande(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une commande.")
            return
        if messagebox.askyesno("Confirmer", "Supprimer cette commande ?"):
            core.delete_commande(self.conn, self.selected_id)
            self.selected_id = None
            self.refresh()

    def refresh(self):
        self._refresh_fournisseur_values()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in core.list_commandes(self.conn):
            tags = ("depasse",) if (c["depassement_livraison"] or c["depassement_paiement"]) else ()
            self.tree.insert("", "end", tags=tags, values=(
                c["id"], c["raison_sociale"], c["piece"] or "", c["libelle"] or "",
                f"{c['montant']:,.2f}", core.to_display_date(c["date_commande"]),
                core.to_display_date(c["date_livraison_prevue"]), c["statut_livraison"],
                core.to_display_date(c["date_echeance_paiement"]), c["statut_paiement"],
            ))


class ExercicesTab(ttk.Frame):
    """Liste des exercices comptables et clôture annuelle."""

    def __init__(self, parent, conn, app):
        super().__init__(parent)
        self.conn = conn
        self.app = app
        ttk.Label(self, text="EXERCICES COMPTABLES", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Label(self, text=(
            "La clôture calcule le solde de clôture de chaque compte de bilan (classes 1 à 5) de "
            "l'exercice sélectionné, l'intègre au résultat net dans le compte 121000 (Report à "
            "nouveau créditeur), et reporte le tout comme solde d'ouverture de l'exercice suivant. "
            "Un exercice clôturé passe en lecture seule : impossible d'y ajouter, modifier ou "
            "supprimer une écriture."
        ), foreground="#595959", wraplength=1000).pack(anchor="w", padx=16, pady=(0, 8))

        cols = ("exercice", "statut")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        self.tree.heading("exercice", text="Exercice")
        self.tree.heading("statut", text="Statut")
        self.tree.column("exercice", width=100, anchor="w")
        self.tree.column("statut", width=150, anchor="w")
        self.tree.pack(fill="x", padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.selected_exercice = None
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=16, pady=4)
        ttk.Button(btns, text="Basculer sur cet exercice", command=self._switch).pack(side="left", padx=2)
        ttk.Button(btns, text="Clôturer l'exercice sélectionné", command=self._close).pack(side="left", padx=2)

        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_exercice = self.tree.item(sel[0], "values")[0]

    def _switch(self):
        if not self.selected_exercice:
            messagebox.showinfo("Info", "Sélectionnez d'abord un exercice.")
            return
        core.set_current_exercice(self.conn, self.selected_exercice)
        self.app._refresh_exercice_list()
        self.app.refresh_current_page()

    def _close(self):
        if not self.selected_exercice:
            messagebox.showinfo("Info", "Sélectionnez d'abord un exercice.")
            return
        ex = self.selected_exercice
        if core.is_exercice_cloture(self.conn, ex):
            messagebox.showinfo("Info", f"L'exercice {ex} est déjà clôturé.")
            return
        bilan = core.compute_bilan(self.conn, exercice=ex)
        if abs(bilan["ecart"]) >= 1:
            if not messagebox.askyesno(
                "Bilan non équilibré",
                f"Le Bilan de l'exercice {ex} n'est pas équilibré (écart de {bilan['ecart']:,.2f}). "
                f"Clôturer quand même ?"
            ):
                return
        resultat_net = bilan['passif']["Résultat net de l'exercice"]
        if not messagebox.askyesno(
            "Confirmer la clôture",
            f"Clôturer définitivement l'exercice {ex} ?\n\n"
            f"Résultat net : {resultat_net:,.2f}\n"
            f"Cette action reporte les soldes de clôture comme soldes d'ouverture de l'exercice "
            f"suivant et verrouille l'exercice {ex} en lecture seule."
        ):
            return
        try:
            next_ex = core.close_exercice(self.conn, ex)
        except ValueError as exc:
            messagebox.showerror("Erreur", str(exc))
            return
        messagebox.showinfo("Clôture effectuée",
                             f"Exercice {ex} clôturé. Les soldes d'ouverture de {next_ex} ont été calculés.")
        core.set_current_exercice(self.conn, next_ex)
        self.app._refresh_exercice_list()
        self.app.refresh_current_page()
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for e in core.list_exercices(self.conn):
            statut = "Clôturé" if e["cloture"] else "Ouvert"
            self.tree.insert("", "end", values=(e["exercice"], statut))


class PlanComptableTab(ttk.Frame):
    """Créer / modifier / supprimer des comptes du Plan comptable."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="PLAN COMPTABLE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        search_bar = ttk.Frame(self)
        search_bar.pack(fill="x", padx=16, pady=4)
        ttk.Label(search_bar, text="Rechercher (code ou libellé) :").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=6)
        search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16, pady=6)
        ttk.Label(form, text="N° Compte :").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.code_var, width=16).grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.label_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.label_var, width=45).grid(row=0, column=3, padx=6)
        ttk.Button(form, text="Créer / Modifier", command=self.save).grid(row=0, column=4, padx=6)
        ttk.Button(form, text="Supprimer le compte sélectionné", command=self.delete).grid(row=0, column=5, padx=6)

        cols = ("code", "label", "classe")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé", "Classe"]
        widths = [110, 500, 70]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.code_var.set(values[0])
        self.label_var.set(values[1])

    def save(self):
        code = self.code_var.get().strip()
        label = self.label_var.get().strip()
        if not code or not label:
            messagebox.showwarning("Champs manquants", "N° Compte et Libellé sont obligatoires.")
            return
        core.add_account(self.conn, code, label)
        self.refresh()

    def delete(self):
        code = self.code_var.get().strip()
        if not code:
            messagebox.showinfo("Info", "Sélectionnez d'abord un compte.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer le compte {code} ?"):
            core.delete_account(self.conn, code)
            self.code_var.set("")
            self.label_var.set("")
            self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for a in core.search_accounts(self.conn, self.search_var.get(), limit=200):
            self.tree.insert("", "end", values=(a["code"], a["label"], a["classe"]))


class _SimplePlanTab(ttk.Frame):
    """Base pour les plans Code + Libellé (analytique, bailleurs)."""
    TITLE = ""
    CODE_LABEL = "Code"

    def list_fn(self, conn):
        raise NotImplementedError

    def add_fn(self, conn, code, label):
        raise NotImplementedError

    def delete_fn(self, conn, code):
        raise NotImplementedError

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text=self.TITLE, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16, pady=6)
        ttk.Label(form, text=self.CODE_LABEL + " :").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.code_var, width=20).grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.label_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.label_var, width=45).grid(row=0, column=3, padx=6)
        ttk.Button(form, text="Créer / Modifier", command=self.save).grid(row=0, column=4, padx=6)
        ttk.Button(form, text="Supprimer", command=self.delete).grid(row=0, column=5, padx=6)

        cols = ("code", "label")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, h, w in zip(cols, [self.CODE_LABEL, "Libellé"], [140, 500]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.code_var.set(values[0])
        self.label_var.set(values[1])

    def save(self):
        code = self.code_var.get().strip()
        label = self.label_var.get().strip()
        if not code or not label:
            messagebox.showwarning("Champs manquants", f"{self.CODE_LABEL} et Libellé sont obligatoires.")
            return
        self.add_fn(self.conn, code, label)
        self.refresh()

    def delete(self):
        code = self.code_var.get().strip()
        if not code:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer « {code} » ?"):
            self.delete_fn(self.conn, code)
            self.code_var.set("")
            self.label_var.set("")
            self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.list_fn(self.conn):
            self.tree.insert("", "end", values=(item["code"], item["label"]))


class PlanAnalytiqueTab(_SimplePlanTab):
    TITLE = "PLAN ANALYTIQUE"
    CODE_LABEL = "Code analytique"

    def list_fn(self, conn):
        return core.list_analytic_codes(conn)

    def add_fn(self, conn, code, label):
        core.add_analytic_code(conn, code, label)

    def delete_fn(self, conn, code):
        core.delete_analytic_code(conn, code)


class PlanBailleurTab(_SimplePlanTab):
    TITLE = "PLAN BAILLEURS DE FONDS"
    CODE_LABEL = "Code bailleur"

    def list_fn(self, conn):
        return core.list_donor_codes(conn)

    def add_fn(self, conn, code, label):
        core.add_donor_code(conn, code, label)

    def delete_fn(self, conn, code):
        core.delete_donor_code(conn, code)


class PlanBudgetaireTab(ttk.Frame):
    """Plan budgétaire : Code + Libellé + Montant prévu."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="PLAN BUDGÉTAIRE", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16, pady=6)
        ttk.Label(form, text="Code budgétaire :").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.code_var, width=16).grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Libellé :").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.label_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.label_var, width=35).grid(row=0, column=3, padx=6)
        ttk.Label(form, text="Montant prévu :").grid(row=0, column=4, sticky="w", padx=(16, 0))
        self.montant_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.montant_var, width=16).grid(row=0, column=5, padx=6)
        ttk.Button(form, text="Créer / Modifier", command=self.save).grid(row=0, column=6, padx=6)
        ttk.Button(form, text="Supprimer", command=self.delete).grid(row=0, column=7, padx=6)

        cols = ("code", "label", "montant")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, h, w in zip(cols, ["Code budgétaire", "Libellé", "Montant prévu"], [120, 400, 130]):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.refresh()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.code_var.set(values[0])
        self.label_var.set(values[1])
        self.montant_var.set(values[2])

    def save(self):
        code = self.code_var.get().strip()
        label = self.label_var.get().strip()
        try:
            montant = float(self.montant_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Le montant prévu doit être un nombre.")
            return
        if not code or not label:
            messagebox.showwarning("Champs manquants", "Code budgétaire et Libellé sont obligatoires.")
            return
        core.add_budget_code(self.conn, code, label, montant)
        self.refresh()

    def delete(self):
        code = self.code_var.get().strip()
        if not code:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer « {code} » ?"):
            core.delete_budget_code(self.conn, code)
            self.code_var.set("")
            self.label_var.set("")
            self.montant_var.set("")
            self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in core.list_budget_codes(self.conn):
            self.tree.insert("", "end", values=(item["code"], item["label"], f"{item['montant']:,.2f}"))


if __name__ == "__main__":
    App().mainloop()
