"""
core.py — Moteur comptable (sans interface graphique).

Toute la logique métier vit ici, indépendamment de Tkinter, pour rester
testable en ligne de commande. main.py ne fait qu'appeler ces fonctions.
"""
import json
import os
import sys
import sqlite3
from datetime import date


def _resource_dir():
    """Dossier des ressources bundlées : gère le cas exécutable PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Comptes SYSCOHADA "spéciaux" utilisés par les calculs automatiques
# (repris de la maquette Excel d'origine).
# ---------------------------------------------------------------------------
COMPTES_STOCK = ["310000", "320000", "331000", "360000"]
COMPTES_TRESORERIE = ["521000", "531000", "570000", "585000"]
COMPTES_CAPITAL = ["101000", "118000", "121000"]
COMPTE_SUBVENTIONS = "141000"
COMPTE_PROVISIONS = "191000"
COMPTES_DETTES_FIN = ["162000", "165000"]
COMPTES_PRODUITS_EXPL = ["701000", "702000", "705000", "706000"]
COMPTE_SUBV_EXPL = "710000"
COMPTE_AUTRES_PRODUITS = "758000"
COMPTES_ACHATS = ["601000", "602000", "604000", "605000"]
COMPTES_TRANSPORT = ["610000", "614000"]
COMPTES_SERVICES_EXT = ["622000", "624000", "625000", "626000", "627000", "628000",
                         "631000", "632000", "633000"]
COMPTES_IMPOTS = ["641000", "645000"]
COMPTE_AUTRES_CHARGES = "651000"
COMPTES_PERSONNEL = ["661000", "663000", "664000"]
COMPTES_DOTATIONS = ["681000", "691000"]
COMPTES_PRODUITS_FIN = ["771000", "776000"]
COMPTES_CHARGES_FIN = ["671000", "676000"]


def default_db_path():
    """Emplacement du fichier de données, à côté de l'exécutable."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "SaisieComptable")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "comptabilite.db")


def get_connection(db_path=None):
    db_path = db_path or default_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            code TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            classe TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            piece TEXT,
            journal TEXT,
            compte TEXT NOT NULL,
            tiers TEXT,
            libelle TEXT,
            debit REAL NOT NULL DEFAULT 0,
            credit REAL NOT NULL DEFAULT 0,
            flux_code TEXT,
            analytic_code TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    _migrate(conn)
    if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
        load_plan_comptable(conn)


def _migrate(conn):
    """Ajoute les colonnes manquantes si la base a été créée par une version antérieure."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(entries)")]
    if "analytic_code" not in cols:
        conn.execute("ALTER TABLE entries ADD COLUMN analytic_code TEXT")
    conn.commit()


def get_setting(conn, key, default=0.0):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return float(row["value"]) if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()


def load_plan_comptable(conn, json_path=None):
    """Charge le plan comptable (bundlé avec l'application) dans la base."""
    if json_path is None:
        json_path = os.path.join(_resource_dir(), "plan_comptable.json")
    with open(json_path, encoding="utf-8") as f:
        accounts = json.load(f)
    conn.executemany(
        "INSERT OR REPLACE INTO accounts (code, label, classe) VALUES (?, ?, ?)",
        [(a["code"], a["label"], a["classe"]) for a in accounts],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Comptes
# ---------------------------------------------------------------------------
def search_accounts(conn, query, limit=50):
    query = (query or "").strip()
    if not query:
        rows = conn.execute("SELECT code, label, classe FROM accounts ORDER BY code LIMIT ?", (limit,))
    else:
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT code, label, classe FROM accounts "
            "WHERE code LIKE ? OR label LIKE ? ORDER BY code LIMIT ?",
            (f"{query}%", like, limit),
        )
    return [dict(r) for r in rows]


def get_account_label(conn, code):
    row = conn.execute("SELECT label FROM accounts WHERE code = ?", (code,)).fetchone()
    return row["label"] if row else "Compte introuvable"


# ---------------------------------------------------------------------------
# Écritures (Saisie)
# ---------------------------------------------------------------------------
def add_entry(conn, date_str, piece, journal, compte, tiers, libelle, debit, credit,
              flux_code="", analytic_code=""):
    conn.execute(
        """INSERT INTO entries (date, piece, journal, compte, tiers, libelle, debit, credit,
                                 flux_code, analytic_code)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date_str, piece, journal, compte, tiers, libelle, debit or 0, credit or 0,
         flux_code, analytic_code),
    )
    conn.commit()


def update_entry(conn, entry_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE entries SET {cols} WHERE id = ?", (*fields.values(), entry_id))
    conn.commit()


def delete_entry(conn, entry_id):
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()


def list_entries(conn, order_by="date"):
    rows = conn.execute(f"SELECT * FROM entries ORDER BY {order_by}, id").fetchall()
    return [dict(r) for r in rows]


def totals_debit_credit(conn):
    row = conn.execute("SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c FROM entries").fetchone()
    return row["d"], row["c"]


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------
def compute_balance(conn, only_with_movement=True):
    rows = conn.execute("""
        SELECT a.code, a.label, a.classe,
               COALESCE(SUM(e.debit), 0)  AS debit,
               COALESCE(SUM(e.credit), 0) AS credit
        FROM accounts a
        LEFT JOIN entries e ON e.compte = a.code
        GROUP BY a.code, a.label, a.classe
        ORDER BY a.code
    """).fetchall()
    result = []
    for r in rows:
        debit, credit = r["debit"], r["credit"]
        if only_with_movement and debit == 0 and credit == 0:
            continue
        result.append({
            "code": r["code"], "label": r["label"], "classe": r["classe"],
            "debit": debit, "credit": credit, "solde": debit - credit,
        })
    return result


def _sum_accounts(balance, codes):
    by_code = {b["code"]: b for b in balance}
    debit = sum(by_code[c]["debit"] for c in codes if c in by_code)
    credit = sum(by_code[c]["credit"] for c in codes if c in by_code)
    return debit, credit


def _sum_class(balance, classe, sign=None):
    total = 0
    for b in balance:
        if b["classe"] != classe:
            continue
        if sign == "pos" and b["solde"] <= 0:
            continue
        if sign == "neg" and b["solde"] >= 0:
            continue
        total += b["solde"]
    return total


# ---------------------------------------------------------------------------
# Compte de résultat
# ---------------------------------------------------------------------------
def compute_compte_resultat(conn):
    balance = compute_balance(conn, only_with_movement=False)

    def net_produit(codes):
        d, c = _sum_accounts(balance, codes)
        return c - d

    def net_charge(codes):
        d, c = _sum_accounts(balance, codes)
        return d - c

    produits = {
        "Ventes (marchandises, produits finis, travaux, services)": net_produit(COMPTES_PRODUITS_EXPL),
        "Subventions d'exploitation": net_produit([COMPTE_SUBV_EXPL]),
        "Autres produits": net_produit([COMPTE_AUTRES_PRODUITS]),
    }
    total_produits = sum(produits.values())

    charges = {
        "Achats (marchandises et matières)": net_charge(COMPTES_ACHATS),
        "Transports": net_charge(COMPTES_TRANSPORT),
        "Services extérieurs": net_charge(COMPTES_SERVICES_EXT),
        "Impôts et taxes": net_charge(COMPTES_IMPOTS),
        "Autres charges": net_charge([COMPTE_AUTRES_CHARGES]),
        "Charges de personnel": net_charge(COMPTES_PERSONNEL),
        "Dotations aux amortissements et provisions": net_charge(COMPTES_DOTATIONS),
    }
    total_charges = sum(charges.values())

    resultat_exploitation = total_produits - total_charges

    produits_fin = net_produit(COMPTES_PRODUITS_FIN)
    charges_fin = net_charge(COMPTES_CHARGES_FIN)
    resultat_financier = produits_fin - charges_fin

    resultat_net = resultat_exploitation + resultat_financier

    return {
        "produits": produits, "total_produits": total_produits,
        "charges": charges, "total_charges": total_charges,
        "resultat_exploitation": resultat_exploitation,
        "produits_financiers": produits_fin, "charges_financieres": charges_fin,
        "resultat_financier": resultat_financier,
        "resultat_net": resultat_net,
    }


# ---------------------------------------------------------------------------
# Bilan
# ---------------------------------------------------------------------------
def compute_bilan(conn, stock_initial=0.0):
    balance = compute_balance(conn, only_with_movement=False)
    cr = compute_compte_resultat(conn)

    immo_brutes = sum(b["solde"] for b in balance if b["classe"] == "2" and int(b["code"]) < 280000)
    amortissements = sum(b["solde"] for b in balance if b["classe"] == "2" and int(b["code"]) >= 280000)
    immo_nettes = immo_brutes + amortissements

    stock_debit, stock_credit = _sum_accounts(balance, COMPTES_STOCK)
    stocks = stock_initial + stock_debit - stock_credit

    creances = _sum_class(balance, "4", sign="pos")
    treso_actif = _sum_class(balance, "5", sign="pos")
    total_actif = immo_nettes + stocks + creances + treso_actif

    capital_d, capital_c = _sum_accounts(balance, COMPTES_CAPITAL)
    capital = capital_c - capital_d
    subv_d, subv_c = _sum_accounts(balance, [COMPTE_SUBVENTIONS])
    subventions = subv_c - subv_d
    prov_d, prov_c = _sum_accounts(balance, [COMPTE_PROVISIONS])
    provisions = prov_c - prov_d
    resultat_net = cr["resultat_net"]
    dettes_fin_d, dettes_fin_c = _sum_accounts(balance, COMPTES_DETTES_FIN)
    dettes_financieres = dettes_fin_c - dettes_fin_d
    dettes_circulantes = -_sum_class(balance, "4", sign="neg")
    treso_passif = -_sum_class(balance, "5", sign="neg")
    total_passif = (capital + subventions + provisions + resultat_net
                     + dettes_financieres + dettes_circulantes + treso_passif)

    return {
        "actif": {
            "Immobilisations brutes": immo_brutes,
            "Amortissements (à déduire)": amortissements,
            "Immobilisations nettes": immo_nettes,
            "Stocks": stocks,
            "Créances et emplois assimilés": creances,
            "Trésorerie actif": treso_actif,
        },
        "total_actif": total_actif,
        "passif": {
            "Capital et réserves": capital,
            "Subventions d'investissement": subventions,
            "Provisions pour risques et charges": provisions,
            "Résultat net de l'exercice": resultat_net,
            "Dettes financières": dettes_financieres,
            "Dettes circulantes": dettes_circulantes,
            "Trésorerie passif": treso_passif,
        },
        "total_passif": total_passif,
        "ecart": total_actif - total_passif,
    }


def compute_grand_livre(conn, compte, tiers=None, date_from=None, date_to=None):
    """Détail chronologique des écritures d'un compte, avec solde cumulé."""
    query = "SELECT * FROM entries WHERE compte = ?"
    params = [compte]
    if tiers:
        query += " AND tiers LIKE ?"
        params.append(f"%{tiers}%")
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " ORDER BY date, id"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    solde = 0.0
    for r in rows:
        solde += r["debit"] - r["credit"]
        r["solde_cumule"] = solde
    return rows


# ---------------------------------------------------------------------------
# Stocks
# ---------------------------------------------------------------------------
def compute_stocks(conn):
    balance = compute_balance(conn, only_with_movement=False)
    by_code = {b["code"]: b for b in balance}
    result = []
    for code in COMPTES_STOCK:
        b = by_code.get(code, {"label": get_account_label(conn, code), "debit": 0.0, "credit": 0.0})
        initial = get_setting(conn, f"stock_initial_{code}", 0.0)
        entrees, sorties = b["debit"], b["credit"]
        result.append({
            "code": code, "label": b["label"], "stock_initial": initial,
            "entrees": entrees, "sorties": sorties,
            "stock_final": initial + entrees - sorties,
        })
    return result


def set_stock_initial(conn, code, value):
    set_setting(conn, f"stock_initial_{code}", value)


# ---------------------------------------------------------------------------
# Production / coûts de fabrication (écritures taguées analytic_code = AN-FAB)
# ---------------------------------------------------------------------------
FLUX_FAB = "AN-FAB"
FAB_POSTES = [
    ("Matières premières et fournitures consommées", ["602000", "604000"]),
    ("Main-d'œuvre directe de production", ["661000", "663000", "664000"]),
    ("Charges indirectes de fabrication", ["624000", "625000", "681000"]),
]


def compute_production(conn):
    balance = compute_balance(conn, only_with_movement=False)

    def net_produit(codes):
        d, c = _sum_accounts(balance, codes)
        return c - d

    ventes = net_produit(["702000", "705000", "706000"])
    stock_d, stock_c = _sum_accounts(balance, ["360000"])
    production_stockee = stock_d - stock_c
    valeur_production = ventes + production_stockee

    postes = []
    total_cout = 0.0
    for label, codes in FAB_POSTES:
        placeholders = ",".join("?" * len(codes))
        row = conn.execute(
            f"SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c FROM entries "
            f"WHERE compte IN ({placeholders}) AND analytic_code = ?",
            (*codes, FLUX_FAB),
        ).fetchone()
        montant = row["d"] - row["c"]
        postes.append({"label": label, "comptes": ", ".join(codes), "montant": montant})
        total_cout += montant

    return {
        "ventes": ventes,
        "production_stockee": production_stockee,
        "valeur_production": valeur_production,
        "postes_cout": postes,
        "cout_production": total_cout,
        "marge": valeur_production - total_cout,
    }


def compute_tft(conn, treso_ouverture=0.0):
    balance = compute_balance(conn, only_with_movement=False)
    treso_debit, treso_credit = _sum_accounts(balance, COMPTES_TRESORERIE)
    variation_totale = treso_debit - treso_credit

    def flux(code):
        d = c = 0.0
        rows = conn.execute(
            "SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c FROM entries "
            "WHERE compte IN (%s) AND flux_code = ?" % ",".join("?" * len(COMPTES_TRESORERIE)),
            (*COMPTES_TRESORERIE, code),
        ).fetchone()
        return rows["d"] - rows["c"]

    exploitation = flux("FLUX-EXP")
    investissement = flux("FLUX-INV")
    financement = flux("FLUX-FIN")
    non_classes = variation_totale - (exploitation + investissement + financement)

    cloture = treso_ouverture + variation_totale
    return {
        "ouverture": treso_ouverture,
        "exploitation": exploitation,
        "investissement": investissement,
        "financement": financement,
        "non_classes": non_classes,
        "variation": variation_totale,
        "cloture": cloture,
    }


if __name__ == "__main__":
    # Petit auto-test en ligne de commande (sans Tkinter).
    conn = get_connection(":memory:" if False else "test_core.db")
    print("Comptes chargés :", conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0])

    add_entry(conn, str(date.today()), "FA-0001", "AC", "601000", "", "Achat marchandises", 1000, 0)
    add_entry(conn, str(date.today()), "FA-0001", "AC", "445200", "", "TVA récupérable", 200, 0)
    add_entry(conn, str(date.today()), "FA-0001", "AC", "401000", "Ets Dupont", "Facture FA-0001", 0, 1200)
    add_entry(conn, str(date.today()), "FV-0001", "VE", "411000", "Société ABC", "Facture FV-0001", 1180, 0)
    add_entry(conn, str(date.today()), "FV-0001", "VE", "701000", "", "Vente marchandises", 0, 1180)

    d, c = totals_debit_credit(conn)
    print("Total débit / crédit :", d, c, "Équilibré :", d == c)

    print("\n--- Balance ---")
    for b in compute_balance(conn):
        print(b)

    print("\n--- Compte de résultat ---")
    cr = compute_compte_resultat(conn)
    print("Résultat net :", cr["resultat_net"])

    print("\n--- Bilan ---")
    bilan = compute_bilan(conn)
    print("Total actif :", bilan["total_actif"], "Total passif :", bilan["total_passif"], "Écart :", bilan["ecart"])

    print("\n--- TFT ---")
    print(compute_tft(conn))

    print("\n--- Grand livre (411000) ---")
    for r in compute_grand_livre(conn, "411000"):
        print(r)

    print("\n--- Stocks ---")
    for s in compute_stocks(conn):
        print(s)

    print("\n--- Production ---")
    print(compute_production(conn))

    conn.close()
    os.remove("test_core.db")
