# -*- coding: utf-8 -*-
"""
SERVEUR — expose le moteur comptable (core.py) sur le réseau local ou
Internet, pour que plusieurs postes « client » (voir client_main.py)
puissent travailler EN MÊME TEMPS sur la même base de données.

Architecture :
- HTTP + JSON, avec la bibliothèque standard Python uniquement (aucune
  dépendance supplémentaire — cohérent avec le reste du projet).
- Une seule base SQLite partagée, en mode WAL (Write-Ahead Logging) pour
  de bonnes performances en lecture/écriture concurrente, protégée par un
  verrou global pour sérialiser les écritures (une opération métier à la
  fois — le moteur comptable n'a pas été conçu pour une écriture
  simultanée sur les mêmes lignes, donc cette sérialisation garantit la
  cohérence des données, au prix d'un débit plus faible qu'un vrai SGBD
  multi-utilisateur — largement suffisant pour une équipe).
- Authentification par utilisateur/mot de passe (table `utilisateurs`,
  déjà existante — voir core.verify_password()), avec un jeton de session
  à durée de vie limitée.
- Liste blanche explicite des fonctions core.py accessibles à distance
  (voir RPC_WHITELIST ci-dessous) — pour ne jamais exposer l'exécution de
  code arbitraire sur le serveur.

Lancement :
    python server.py [--port 8765] [--db chemin/vers/comptabilite.db]

IMPORTANT — sécurité réseau :
- Sur un réseau LOCAL (même bureau/même box internet), aucune configuration
  supplémentaire n'est nécessaire : les postes clients se connectent à
  l'adresse IP locale du serveur (ex. 192.168.1.10) sur le port choisi.
- Pour un accès depuis INTERNET (hors réseau local), il faut soit :
  (a) configurer une redirection de port (« port forwarding ») sur le
      routeur/box vers ce serveur, avec un mot de passe fort pour chaque
      utilisateur — le trafic reste alors en clair (HTTP), donc réservé à
      un usage de confiance (VPN recommandé en plus si possible) ; soit
  (b) placer le serveur derrière un VPN d'entreprise, solution la plus
      sûre pour un accès distant.
Ce serveur n'implémente PAS le chiffrement TLS/HTTPS par défaut — à
prévoir séparément (ex. reverse proxy) pour un usage sur Internet ouvert.
"""
import argparse
import json
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core

# ---------------------------------------------------------------------------
# Configuration de la liste blanche des fonctions accessibles à distance —
# circuit commercial complet (Saisie + Ventes + Achats + Stocks), voir la
# demande initiale. Étendre cette liste au fur et à mesure que d'autres
# écrans du client sont adaptés (même principe pour tout autre module).
# ---------------------------------------------------------------------------
RPC_WHITELIST = {
    # Liste large — la quasi-totalite des fonctions metier de core.py sont
    # autorisees a distance (le filtrage par PROFIL reste gere cote client par
    # les menus autorises -- voir core.get_menus_autorises()) ; seules les
    # operations sensibles (gestion des utilisateurs/niveaux, reinitialisation
    # des donnees, mots de passe) et les fonctions travaillant sur des fichiers
    # LOCAUX AU SERVEUR (export_*/import_*_xlsx, generate_etat_xlsx) restent
    # exclues -- regenerer cette liste via le script utilise pour la construire
    # si necessaire (voir README).
    "add_account", "add_analytic_code", "add_balanced_entry", "add_budget_code", "add_client", "add_commande",
    "add_donor_code", "add_ecriture_multi_lignes", "add_entry", "add_facture", "add_fournisseur", "add_hs",
    "add_kpi", "add_ligne_bordereau_livraison", "add_ligne_ep_bon_commande", "add_ligne_expression_besoin",
    "add_ligne_facture_achat", "add_ligne_facture_vente", "add_ligne_reglement", "add_ligne_reparation",
    "add_mission", "add_personnel", "add_piece_rechange", "add_produit_fini", "add_recette_ligne",
    "add_taux_retenue", "add_taux_tva", "add_time_sheet", "add_vehicule",
    "account_exists", "ajouter_codes_analytiques_suggeres", "ajouter_taux_retenue_suggeres",
    "analytic_code_exists", "budget_code_exists", "client_exists", "close_exercice", "donor_code_exists",
    "enregistrer_paiement_facture", "enregistrer_paiement_reglement", "ensure_racine_accounts",
    "fournisseur_exists", "is_exercice_cloture", "niveau_acces_exists", "search_accounts",
    "taux_retenue_exists", "taux_tva_exists", "total_opening_balance", "totals_debit_credit",
    "compute_achats_par_fournisseur", "compute_balance", "compute_balance_agee", "compute_balance_detaillee",
    "compute_bilan", "compute_bilan_detaille", "compute_bilan_mouvement_periode", "compute_bilan_plat",
    "compute_cr", "compute_tft_gabarit", "compute_situation_fin",
    "compute_bilan_solde_ouverture", "compute_compte_resultat", "compute_comptes_prefixe_periode",
    "compute_cout_production", "compute_cout_total_reparation", "compute_cout_unitaire_moyen_analytique",
    "compute_couts_analytiques_categorie", "compute_couts_analytiques_fabrication",
    "compute_ecart_diagnostic", "compute_engagements_a_payer", "compute_ep_bon_commande_totals",
    "compute_etat_formule_generique", "compute_facture_achat_totals", "compute_facture_totals",
    "compute_grand_livre", "compute_grand_livre_complet", "compute_immobilisations_liste",
    "compute_liasse_bilan", "compute_liasse_resultat", "compute_mouvements_prefixe_periode",
    "compute_mouvements_stocks", "compute_pieces_non_equilibrees", "compute_production",
    "compute_reglement_totals", "compute_resultat_net_complet", "compute_situation_financiere",
    "compute_stocks", "compute_stocks_detail", "compute_tableau_bord_grh", "compute_tft",
    "compute_tft_indirect", "compute_tft_officiel", "compute_tresorerie_banques_horizontal",
    "compute_tresorerie_detail", "compute_ventes_par_client",
    "create_bordereau_livraison", "create_ep_bon_commande", "create_expression_besoin",
    "create_facture_achat", "create_facture_vente", "create_reglement", "create_reparation",
    "delete_account", "delete_analytic_code", "delete_bordereau_livraison", "delete_budget_code",
    "delete_client", "delete_commande", "delete_donor_code", "delete_entries_bulk", "delete_entry",
    "delete_ep_bon_commande", "delete_expression_besoin", "delete_facture", "delete_facture_achat",
    "delete_facture_vente", "delete_fournisseur", "delete_hs", "delete_kpi",
    "delete_ligne_bordereau_livraison", "delete_ligne_ep_bon_commande", "delete_ligne_expression_besoin",
    "delete_ligne_facture_achat", "delete_ligne_facture_vente", "delete_ligne_reglement",
    "delete_ligne_reparation", "delete_mission", "delete_personnel", "delete_piece_rechange",
    "delete_produit_fini", "delete_recette_ligne", "delete_reglement", "delete_reparation",
    "delete_taux_retenue", "delete_taux_tva", "delete_time_sheet", "delete_vehicule",
    "devalider_ep_bon_commande", "devalider_facture_achat", "devalider_facture_vente",
    "devalider_paiement_reglement", "devalider_reglement",
    "get_account_label", "get_analytic_code_unite", "get_bordereau_livraison", "get_client",
    "get_company_info", "get_company_value", "get_current_exercice", "get_ep_bon_commande",
    "get_expression_besoin", "get_facture_achat", "get_facture_vente", "get_fournisseur",
    "get_immobilisation_fiche", "get_menus_autorises", "get_opening_balance", "get_personnel",
    "get_piece_balance", "get_piece_rechange", "get_produit_fini", "get_reglement", "get_reparation",
    "get_setting", "get_text_setting", "get_vehicule",
    "list_analytic_codes", "list_bordereaux_livraison", "list_budget_codes", "list_clients", "list_commandes",
    "list_donor_codes", "list_entries", "list_ep_bons_commande", "list_exercices", "list_expressions_besoin",
    "list_factures", "list_factures_achat", "list_factures_vente", "list_fournisseurs", "list_hs", "list_kpi",
    "list_lignes_bordereau_livraison", "list_lignes_ep_bon_commande", "list_lignes_expression_besoin",
    "list_lignes_facture_achat", "list_lignes_facture_vente", "list_lignes_reglement",
    "list_lignes_reparation", "list_missions", "list_niveaux_acces", "list_opening_balances",
    "list_personnel", "list_pieces_rechange", "list_produits_finis", "list_recette_lignes", "list_reglements",
    "list_reparations", "list_taux_amortissement", "list_taux_retenue", "list_taux_tva", "list_time_sheet",
    "list_vehicules",
    "set_company_value", "set_current_exercice", "set_immobilisation_fiche", "set_opening_balance",
    "set_pointage_bancaire", "set_setting", "set_stock_initial", "set_stock_qte_initiale",
    "set_taux_amortissement", "set_text_setting",
    "update_bordereau_livraison", "update_commande", "update_entry", "update_ep_bon_commande",
    "update_expression_besoin", "update_facture", "update_facture_achat", "update_facture_vente", "update_hs",
    "update_kpi", "update_ligne_bordereau_livraison", "update_ligne_ep_bon_commande",
    "update_ligne_reglement", "update_mission", "update_personnel", "update_piece_rechange",
    "update_reglement", "update_reparation", "update_time_sheet", "update_vehicule",
    "valider_bordereau_livraison", "valider_ep_bon_commande", "valider_expression_besoin",
    "valider_fabrication", "valider_facture_achat", "valider_facture_vente", "valider_reglement",
}

SESSION_DURATION_SECONDS = 8 * 3600  # 8h de travail avant reconnexion


class SessionStore:
    """Jetons de session en mémoire — {token: {"utilisateur":..., "niveau_acces":..., "expire":...}}."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self, nom_utilisateur, niveau_acces):
        token = secrets.token_hex(32)
        with self._lock:
            self._sessions[token] = {
                "utilisateur": nom_utilisateur,
                "niveau_acces": niveau_acces,
                "expire": time.time() + SESSION_DURATION_SECONDS,
            }
        return token

    def get(self, token):
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if session["expire"] < time.time():
                del self._sessions[token]
                return None
            return session

    def revoke(self, token):
        with self._lock:
            self._sessions.pop(token, None)


class AccountingServer:
    """Encapsule la connexion SQLite partagée (mode WAL) et le verrou
    global qui sérialise les écritures — un seul point d'accès à la base
    pour toutes les requêtes réseau, quel que soit le thread qui les traite."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        core.init_db(self.conn)
        self.write_lock = threading.RLock()
        self.sessions = SessionStore()

    def call(self, function_name, args, kwargs):
        if function_name not in RPC_WHITELIST:
            raise PermissionError(f"Fonction « {function_name} » non autorisée à distance.")
        fn = getattr(core, function_name, None)
        if fn is None:
            raise AttributeError(f"Fonction « {function_name} » introuvable.")
        with self.write_lock:
            # Clôt toute transaction implicite en attente AVANT d'exécuter la
            # fonction — sans ça, une connexion SQLite longue durée en mode
            # WAL peut rester figée sur un instantané ancien de la base
            # (notamment sous Windows) tant qu'aucune transaction n'est
            # explicitement terminée, même si un AUTRE processus (l'application
            # de bureau) a bien validé des changements depuis. Sans effet si
            # rien n'était en attente (commit() est alors un no-op).
            self.conn.commit()
            return fn(self.conn, *args, **kwargs)


def _json_default(obj):
    """Sérialisation JSON pour les types non natifs (ex. sqlite3.Row déjà
    converti en dict par les fonctions core.py, mais par prudence)."""
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def make_handler(server_state: AccountingServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SaisieComptableServer/1.0"

        def log_message(self, format, *args):
            pass  # silencieux — évite de polluer la console ; activer si besoin de diagnostic

        def _send_json(self, status, payload):
            body = json.dumps(payload, default=_json_default, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_POST(self):
            try:
                if self.path == "/login":
                    return self._handle_login()
                if self.path == "/rpc":
                    return self._handle_rpc()
                if self.path == "/logout":
                    return self._handle_logout()
                self._send_json(404, {"ok": False, "error": "Route inconnue."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": f"Erreur serveur : {exc}"})

        def do_GET(self):
            if self.path == "/ping":
                return self._send_json(200, {"ok": True, "message": "Serveur SaisieComptable actif."})
            self._send_json(404, {"ok": False, "error": "Route inconnue."})

        def _handle_login(self):
            data = self._read_json_body()
            nom_utilisateur = (data.get("nom_utilisateur") or "").strip()
            mot_de_passe = data.get("mot_de_passe") or ""
            if not nom_utilisateur or not mot_de_passe:
                return self._send_json(400, {"ok": False, "error": "Identifiant et mot de passe requis."})
            with server_state.write_lock:
                server_state.conn.commit()  # voir AccountingServer.call() -- force une lecture a jour (WAL)
                utilisateur = core.verify_password(server_state.conn, nom_utilisateur, mot_de_passe)
                if utilisateur:
                    menus_autorises = sorted(core.get_menus_autorises(server_state.conn, utilisateur.get("niveau_acces")))
            if not utilisateur:
                return self._send_json(401, {"ok": False, "error": "Identifiant ou mot de passe incorrect."})
            token = server_state.sessions.create(nom_utilisateur, utilisateur.get("niveau_acces"))
            self._send_json(200, {
                "ok": True,
                "session": token,
                "utilisateur": nom_utilisateur,
                "menus_autorises": menus_autorises,
                "niveau_acces": utilisateur.get("niveau_acces"),
            })

        def _handle_logout(self):
            data = self._read_json_body()
            token = data.get("session")
            if token:
                server_state.sessions.revoke(token)
            self._send_json(200, {"ok": True})

        def _handle_rpc(self):
            data = self._read_json_body()
            token = data.get("session")
            session = server_state.sessions.get(token) if token else None
            if not session:
                return self._send_json(401, {"ok": False, "error": "Session expirée ou invalide — reconnectez-vous."})

            function_name = data.get("function")
            args = data.get("args") or []
            kwargs = data.get("kwargs") or {}
            try:
                result = server_state.call(function_name, args, kwargs)
            except PermissionError as exc:
                return self._send_json(403, {"ok": False, "error": str(exc)})
            except Exception as exc:
                return self._send_json(400, {"ok": False, "error": f"{type(exc).__name__} : {exc}"})
            self._send_json(200, {"ok": True, "result": result})

    return Handler


def run_server(db_path, host="0.0.0.0", port=8765):
    state = AccountingServer(db_path)
    handler_cls = make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    print(f"Serveur SaisieComptable démarré sur {host}:{port}")
    print(f"Base de données : {db_path}")
    print("Adresses locales possibles pour les postes clients : voir 'ipconfig' (Windows) sur cette machine.")
    print("Ctrl+C pour arrêter.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        httpd.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur SaisieComptable — accès réseau multi-utilisateur.")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute (défaut : 8765)")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute (défaut : 0.0.0.0, toutes les interfaces)")
    parser.add_argument("--db", default=None, help="Chemin de la base de données (défaut : emplacement standard)")
    args = parser.parse_args()
    db_path = args.db or core.default_db_path()
    run_server(db_path, host=args.host, port=args.port)
