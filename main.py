"""
main.py — Application de comptabilité SYSCOHADA autonome (Tkinter).

Lance une fenêtre avec 4 onglets : Saisie, Balance, Compte de résultat, Bilan.
Les données sont stockées localement dans un fichier SQLite
(%LOCALAPPDATA%\\SaisieComptable\\comptabilite.db sous Windows).
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import core


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Saisie Comptable SYSCOHADA")
        self.geometry("1150x650")
        self.conn = core.get_connection()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.saisie_tab = SaisieTab(notebook, self.conn)
        self.grand_livre_tab = GrandLivreTab(notebook, self.conn)
        self.balance_tab = BalanceTab(notebook, self.conn)
        self.stocks_tab = StocksTab(notebook, self.conn)
        self.production_tab = ProductionTab(notebook, self.conn)
        self.cr_tab = CompteResultatTab(notebook, self.conn)
        self.bilan_tab = BilanTab(notebook, self.conn)
        self.tft_tab = TftTab(notebook, self.conn)

        notebook.add(self.saisie_tab, text="Saisie")
        notebook.add(self.grand_livre_tab, text="Grand livre")
        notebook.add(self.balance_tab, text="Balance")
        notebook.add(self.stocks_tab, text="Stocks")
        notebook.add(self.production_tab, text="Production")
        notebook.add(self.cr_tab, text="Compte de résultat")
        notebook.add(self.bilan_tab, text="Bilan")
        notebook.add(self.tft_tab, text="TFT")

        # Rafraîchir les onglets de synthèse quand on les affiche
        notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())

    def refresh_all(self):
        self.grand_livre_tab.refresh()
        self.balance_tab.refresh()
        self.stocks_tab.refresh()
        self.production_tab.refresh()
        self.cr_tab.refresh()
        self.bilan_tab.refresh()
        self.tft_tab.refresh()


class SaisieTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.selected_id = None
        self._build()
        self.refresh()

    def _build(self):
        form = ttk.LabelFrame(self, text="Écriture")
        form.pack(fill="x", padx=8, pady=8)

        labels = ["Date (AAAA-MM-JJ)", "N° Pièce", "Journal", "N° Compte",
                  "Tiers", "Libellé", "Débit", "Crédit", "Code flux (EXP/INV/FIN)",
                  "Code analytique (ex: AN-FAB)"]
        self.vars = {k: tk.StringVar() for k in labels}
        self.vars["Date (AAAA-MM-JJ)"].set(str(date.today()))

        for i, lbl in enumerate(labels):
            r, c = divmod(i, 3)
            ttk.Label(form, text=lbl).grid(row=r * 2, column=c, sticky="w", padx=4, pady=(4, 0))
            entry = ttk.Entry(form, textvariable=self.vars[lbl], width=24)
            entry.grid(row=r * 2 + 1, column=c, sticky="we", padx=4, pady=(0, 4))
            if lbl == "N° Compte":
                entry.bind("<KeyRelease>", self._show_account_label)
                self.compte_entry = entry

        self.account_label_var = tk.StringVar()
        ttk.Label(form, textvariable=self.account_label_var, foreground="#1F4E78").grid(
            row=8, column=0, columnspan=3, sticky="w", padx=4)

        btns = ttk.Frame(form)
        btns.grid(row=9, column=0, columnspan=3, sticky="w", pady=6, padx=4)
        ttk.Button(btns, text="Ajouter", command=self.add_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Enregistrer modification", command=self.update_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Supprimer", command=self.delete_entry).pack(side="left", padx=2)
        ttk.Button(btns, text="Effacer le formulaire", command=self.clear_form).pack(side="left", padx=2)

        cols = ("id", "date", "piece", "journal", "compte", "libelle_compte",
                "tiers", "libelle", "debit", "credit", "flux", "analytique")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        headers = ["ID", "Date", "Pièce", "Journal", "Compte", "Libellé du compte",
                   "Tiers", "Libellé écriture", "Débit", "Crédit", "Flux", "Analytique"]
        widths = [40, 90, 80, 60, 70, 200, 110, 200, 80, 80, 70, 90]
        for c, h, w in zip(cols, headers, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        totals = ttk.Frame(self)
        totals.pack(fill="x", padx=8, pady=(0, 8))
        self.totals_var = tk.StringVar()
        ttk.Label(totals, textvariable=self.totals_var, font=("Segoe UI", 10, "bold")).pack(side="left")

    def _show_account_label(self, event=None):
        code = self.vars["N° Compte"].get().strip()
        if code:
            self.account_label_var.set(core.get_account_label(self.conn, code))
        else:
            self.account_label_var.set("")

    def _get_form(self):
        try:
            debit = float(self.vars["Débit"].get() or 0)
            credit = float(self.vars["Crédit"].get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Débit et Crédit doivent être des nombres.")
            return None
        return dict(
            date_str=self.vars["Date (AAAA-MM-JJ)"].get().strip(),
            piece=self.vars["N° Pièce"].get().strip(),
            journal=self.vars["Journal"].get().strip(),
            compte=self.vars["N° Compte"].get().strip(),
            tiers=self.vars["Tiers"].get().strip(),
            libelle=self.vars["Libellé"].get().strip(),
            debit=debit,
            credit=credit,
            flux_code=self.vars["Code flux (EXP/INV/FIN)"].get().strip(),
            analytic_code=self.vars["Code analytique (ex: AN-FAB)"].get().strip(),
        )

    def add_entry(self):
        data = self._get_form()
        if not data or not data["compte"] or not data["date_str"]:
            messagebox.showwarning("Champs manquants", "Date et N° Compte sont obligatoires.")
            return
        core.add_entry(self.conn, **data)
        self.clear_form()
        self.refresh()

    def update_entry(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne dans le tableau.")
            return
        data = self._get_form()
        if not data:
            return
        core.update_entry(self.conn, self.selected_id, **data)
        self.clear_form()
        self.refresh()

    def delete_entry(self):
        if self.selected_id is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord une ligne dans le tableau.")
            return
        if messagebox.askyesno("Confirmer", "Supprimer cette écriture ?"):
            core.delete_entry(self.conn, self.selected_id)
            self.clear_form()
            self.refresh()

    def clear_form(self):
        self.selected_id = None
        for k, v in self.vars.items():
            v.set("" if k != "Date (AAAA-MM-JJ)" else str(date.today()))
        self.account_label_var.set("")

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.selected_id = int(values[0])
        self.vars["Date (AAAA-MM-JJ)"].set(values[1])
        self.vars["N° Pièce"].set(values[2])
        self.vars["Journal"].set(values[3])
        self.vars["N° Compte"].set(values[4])
        self.vars["Tiers"].set(values[6])
        self.vars["Libellé"].set(values[7])
        self.vars["Débit"].set(values[8])
        self.vars["Crédit"].set(values[9])
        self.vars["Code flux (EXP/INV/FIN)"].set(values[10])
        self.vars["Code analytique (ex: AN-FAB)"].set(values[11])
        self._show_account_label()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        entries = core.list_entries(self.conn)
        total_d = total_c = 0.0
        for e in entries:
            label = core.get_account_label(self.conn, e["compte"])
            self.tree.insert("", "end", values=(
                e["id"], e["date"], e["piece"] or "", e["journal"] or "", e["compte"], label,
                e["tiers"] or "", e["libelle"] or "",
                f"{e['debit']:.2f}" if e["debit"] else "",
                f"{e['credit']:.2f}" if e["credit"] else "",
                e["flux_code"] or "",
                e["analytic_code"] or "",
            ))
            total_d += e["debit"]
            total_c += e["credit"]
        equilibre = "Équilibré ✓" if abs(total_d - total_c) < 0.01 else "NON ÉQUILIBRÉ ✗"
        self.totals_var.set(f"TOTAUX — Débit : {total_d:,.2f}   Crédit : {total_c:,.2f}   {equilibre}")


class BalanceTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        cols = ("compte", "libelle", "debit", "credit", "solde")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé du compte", "Total Débit", "Total Crédit", "Solde"]
        widths = [90, 320, 110, 110, 110]
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
                b["code"], b["label"], f"{b['debit']:,.2f}", f"{b['credit']:,.2f}", f"{b['solde']:,.2f}"
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
        ttk.Entry(bar, textvariable=self.compte_var, width=14).pack(side="left", padx=4)
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

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        compte = self.compte_var.get().strip()
        if not compte:
            self.label_var.set("")
            return
        self.label_var.set(core.get_account_label(self.conn, compte))
        for r in core.compute_grand_livre(self.conn, compte, self.tiers_var.get().strip() or None):
            self.tree.insert("", "end", values=(
                r["date"], r["piece"] or "", r["journal"] or "", r["tiers"] or "", r["libelle"] or "",
                f"{r['debit']:.2f}" if r["debit"] else "",
                f"{r['credit']:.2f}" if r["credit"] else "",
                f"{r['solde_cumule']:,.2f}",
            ))


class StocksTab(ttk.Frame):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        ttk.Label(self, text="Stock initial : cliquez une ligne, modifiez la valeur puis « Enregistrer ».",
                  foreground="#595959").pack(anchor="w", padx=8, pady=(8, 0))

        edit_bar = ttk.Frame(self)
        edit_bar.pack(fill="x", padx=8, pady=4)
        ttk.Label(edit_bar, text="Stock initial du compte sélectionné :").pack(side="left")
        self.initial_var = tk.StringVar()
        ttk.Entry(edit_bar, textvariable=self.initial_var, width=14).pack(side="left", padx=4)
        ttk.Button(edit_bar, text="Enregistrer", command=self.save_initial).pack(side="left", padx=4)

        cols = ("code", "label", "initial", "entrees", "sorties", "final")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headers = ["N° Compte", "Libellé", "Stock initial", "Entrées (Débit)", "Sorties (Crédit)", "Stock final"]
        widths = [90, 260, 110, 120, 120, 110]
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

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in core.compute_stocks(self.conn):
            self.tree.insert("", "end", values=(
                s["code"], s["label"], f"{s['stock_initial']:,.2f}",
                f"{s['entrees']:,.2f}", f"{s['sorties']:,.2f}", f"{s['stock_final']:,.2f}",
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
        ttk.Label(bar, text="Trésorerie d'ouverture :").pack(side="left")
        self.ouverture_var = tk.StringVar(value=str(core.get_setting(conn, "treso_ouverture", 0.0)))
        ttk.Entry(bar, textvariable=self.ouverture_var, width=14).pack(side="left", padx=4)
        ttk.Button(bar, text="Enregistrer et actualiser", command=self.save_and_refresh).pack(side="left", padx=6)
        ttk.Label(bar, text=(
            "Astuce : les mouvements de trésorerie (521000/531000/570000/585000) se classent "
            "par nature via le code flux EXP / INV / FIN saisi dans l'onglet Saisie."
        ), foreground="#595959", wraplength=650).pack(side="left", padx=12)

        self.text = tk.Text(self, font=("Consolas", 11), wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def save_and_refresh(self):
        try:
            value = float(self.ouverture_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "La trésorerie d'ouverture doit être un nombre.")
            return
        core.set_setting(self.conn, "treso_ouverture", value)
        self.refresh()

    def refresh(self):
        ouverture = core.get_setting(self.conn, "treso_ouverture", 0.0)
        self.ouverture_var.set(str(ouverture))
        t = core.compute_tft(self.conn, treso_ouverture=ouverture)
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


if __name__ == "__main__":
    App().mainloop()
