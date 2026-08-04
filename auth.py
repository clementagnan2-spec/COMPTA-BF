# -*- coding: utf-8 -*-
"""
auth.py
-------
Gestion des deux niveaux d'accès :
  - Administrateur : mot de passe fixe, choisi/changé par l'admin.
      -> accès aux Paramètres de paie ET au mot de passe Utilisateur en cours.
  - Utilisateur : mot de passe qui change automatiquement chaque mois.
      -> accès à la saisie et au calcul de la paie uniquement.

Le mot de passe Utilisateur est dérivé d'une clé secrète (stockée dans le
fichier de données local, jamais dans le code) + le mois en cours, via
HMAC-SHA256. Il est donc imprévisible sans connaître la clé secrète, mais
reproductible automatiquement à chaque changement de mois -- pas besoin
d'une connexion Internet ni d'une action manuelle pour qu'il change.

L'administrateur peut à tout moment :
  - consulter le mot de passe Utilisateur du mois en cours (onglet Sécurité)
  - forcer un mot de passe Utilisateur personnalisé pour le mois en cours
  - régénérer/relancer la clé secrète (ce qui change tous les mots de passe
    futurs, mais PAS ceux déjà communiqués et notés ailleurs)
"""

import hashlib
import hmac
import os
import secrets
import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Hachage du mot de passe Administrateur
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: Optional[bytes] = None):
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(digest.hex(), hash_hex)


# ---------------------------------------------------------------------------
# Mot de passe Utilisateur, régénéré automatiquement chaque mois
# ---------------------------------------------------------------------------

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans caractères ambigus (0/O, 1/I)

MOIS_LABELS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
               "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def _period_key(dt: Optional[datetime.date] = None) -> str:
    """Clé de mois civil, ex: '2026-08' pour août 2026."""
    dt = dt or datetime.date.today()
    return f"{dt.year:04d}-{dt.month:02d}"


def period_label(period: Optional[str] = None) -> str:
    """Libellé lisible du mois, ex: '2026-08' -> 'Août 2026'."""
    period = period or _period_key()
    try:
        year, month = period.split("-")
        return f"{MOIS_LABELS[int(month) - 1]} {year}"
    except Exception:
        return period


def generate_period_password(secret_key_hex: str, period: Optional[str] = None,
                              length: int = 8) -> str:
    """Dérive un mot de passe lisible à partir de la clé secrète + la période
    (ex: '2026-08'). Déterministe : même clé + même mois => même mot de passe."""
    period = period or _period_key()
    secret = bytes.fromhex(secret_key_hex)
    digest = hmac.new(secret, period.encode("utf-8"), hashlib.sha256).digest()

    chars = []
    for byte in digest:
        chars.append(ALPHABET[byte % len(ALPHABET)])
        if len(chars) >= length:
            break

    raw = "".join(chars)
    # formatage lisible : XXXX-XXXX
    if length == 8:
        return f"{raw[:4]}-{raw[4:]}"
    return raw


# Alias conservé pour compatibilité si d'autres fichiers l'appellent encore
# sous son ancien nom.
generate_monthly_password = generate_period_password


def new_secret_key() -> str:
    return secrets.token_hex(32)


def current_period() -> str:
    return _period_key()


def get_effective_user_password(config: dict) -> str:
    """Retourne le mot de passe Utilisateur qui s'applique CE MOIS-CI :
    - un mot de passe forcé par l'admin pour ce mois précis s'il existe,
    - sinon le mot de passe dérivé automatiquement de la clé secrète."""
    period = current_period()
    override = config.get("user_password_overrides", {}).get(period)
    if override:
        return override
    return generate_period_password(config["secret_key"], period)
