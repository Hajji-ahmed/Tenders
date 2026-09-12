"""Commandes d'administration : `uv run python -m app.cli <commande>`.

Le mot de passe n'est jamais passé en argument (il finirait dans l'historique du shell) :
il est lu depuis la variable d'environnement TENDER_PASSWORD ou saisi de façon masquée.
"""

import argparse
import getpass
import os

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User

MIN_PASSWORD_LENGTH = 12


def _read_password() -> str:
    password = os.environ.get("TENDER_PASSWORD") or getpass.getpass("Mot de passe : ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Mot de passe trop court (minimum {MIN_PASSWORD_LENGTH} caractères)")
    return password


def create_user(email: str) -> None:
    email = email.lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print(f"Utilisateur {email} déjà existant (utiliser set-password)")
            return
        db.add(User(email=email, password_hash=hash_password(_read_password())))
        db.commit()
        print(f"Utilisateur {email} créé")


def set_password(email: str) -> None:
    email = email.lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"Utilisateur {email} introuvable")
        user.password_hash = hash_password(_read_password())
        db.commit()
        print(f"Mot de passe de {email} mis à jour")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tender-ai")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-user", help="Créer l'utilisateur principal")
    p_create.add_argument("--email", required=True)

    p_pwd = sub.add_parser("set-password", help="Changer le mot de passe d'un utilisateur")
    p_pwd.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.cmd == "create-user":
        create_user(args.email)
    elif args.cmd == "set-password":
        set_password(args.email)


if __name__ == "__main__":
    main()
