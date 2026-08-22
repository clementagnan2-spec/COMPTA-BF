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
    """Fenêtre principale du client, une fois connecté — pour l'instant,
    l'écran Saisie comptable (pleinement fonctionnel, multi-lignes). Les
    écrans Ventes/Achats/Stocks s'ajouteront selon le même modèle."""

    def __init__(self, remote: RemoteConnection):
        super().__init__()
        self.remote = remote
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

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        saisie_tab = RemoteSaisieTab(notebook, remote)
        notebook.add(saisie_tab, text="SAISIE")

        roadmap_tab = ttk.Frame(notebook)
        ttk.Label(roadmap_tab, text="Prochains écrans du client (même architecture, à venir)",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        for txt in ("Ventes — facturation et suivi clients", "Achats — fournisseurs, bons de commande, règlements",
                    "Stocks — mouvements et valorisation"):
            ttk.Label(roadmap_tab, text=f"• {txt}", foreground="#595959").pack(anchor="w", padx=24, pady=2)
        notebook.add(roadmap_tab, text="À VENIR")

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

    _APPEL_ECHEC = object()  # sentinelle distincte de None (un appel reussi peut legitimement renvoyer None)

    def _appeler(self, fonction, *args, **kwargs):
        """Enveloppe chaque appel réseau avec une gestion d'erreur unifiée
        (session expirée, serveur injoignable, erreur métier). Renvoie
        _APPEL_ECHEC (PAS None) en cas d'échec — pour ne jamais confondre
        un appel réussi qui renvoie légitimement None avec un échec."""
        try:
            return getattr(client_core, fonction)(self.remote, *args, **kwargs)
        except RemoteAuthError as exc:
            messagebox.showerror("Session expirée", str(exc), parent=self)
            self.winfo_toplevel().destroy()
        except RemoteConnectionError as exc:
            messagebox.showerror("Connexion perdue", str(exc), parent=self)
        except RemoteCallError as exc:
            messagebox.showerror("Erreur", str(exc), parent=self)
        return self._APPEL_ECHEC

    def _on_compte_keyrelease(self, event=None):
        query = self.compte_var.get().strip()
        items = self._appeler("search_accounts", query, limit=30)
        if items is not self._APPEL_ECHEC:
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
        if resultat is self._APPEL_ECHEC:
            return  # erreur déjà affichée par _appeler (session expirée, réseau, ou règle métier)
        messagebox.showinfo("Enregistré", f"Écriture « {piece} » enregistrée sur le serveur.", parent=self)
        self.lignes = []
        self._refresh_lignes()
        self.piece_var.set("")
        self.refresh_entries()

    def refresh_entries(self):
        exercice = self._appeler("get_current_exercice")
        if exercice is self._APPEL_ECHEC:
            return
        entries = self._appeler("list_entries", exercice=exercice)
        if entries is self._APPEL_ECHEC:
            return
        for row in self.tree_entries.get_children():
            self.tree_entries.delete(row)
        for e in entries[-200:][::-1]:  # les 200 plus récentes, plus récentes en premier
            self.tree_entries.insert("", "end", values=(
                core.to_display_date(e["date"]), e["piece"], e["journal"], e["compte"], e["libelle"],
                fmt_cfa(e["debit"]) if e["debit"] else "", fmt_cfa(e["credit"]) if e["credit"] else ""))


def main():
    login = LoginWindow()
    login.mainloop()
    if login.remote is None:
        return  # fenêtre fermée sans connexion réussie
    app = ClientApp(login.remote)
    app.mainloop()


if __name__ == "__main__":
    main()
