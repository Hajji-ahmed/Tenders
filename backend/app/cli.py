"""Commandes d'administration : `uv run python -m app.cli <commande>`."""

import argparse

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User


def create_user(email: str, password: str) -> None:
    email = email.lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print(f"Utilisateur {email} déjà existant")
            return
        db.add(User(email=email, password_hash=hash_password(password)))
        db.commit()
        print(f"Utilisateur {email} créé")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tender-ai")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_user = sub.add_parser("create-user", help="Créer l'utilisateur principal")
    p_user.add_argument("--email", required=True)
    p_user.add_argument("--password", required=True)

    args = parser.parse_args()
    if args.cmd == "create-user":
        create_user(args.email, args.password)


if __name__ == "__main__":
    main()
