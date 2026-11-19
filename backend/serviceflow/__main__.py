from argparse import ArgumentParser
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import Settings
from .db import make_engine
from .domain import Role
from .main import initialize
from .models import User
from .schemas import UserCreate
from .seed import reset_demo, seed_demo


def main() -> None:
    parser = ArgumentParser(prog="python -m serviceflow")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("seed-demo", help="Populate an empty database with fictional data.")
    reset = subcommands.add_parser("reset-demo", help="Replace records in a demonstration database.")
    reset.add_argument("--confirm", action="store_true", help="Confirm that changed demonstration records will be lost.")
    bootstrap = subcommands.add_parser("create-admin", help="Create a real account using an interactive password prompt.")
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.command == "reset-demo" and not args.confirm:
        parser.error("Reset deletes changes in the demo workspace. Run with --confirm to continue.")
    payload = None
    if args.command == "create-admin":
        first = getpass("Password: ")
        second = getpass("Confirm password: ")
        if first != second:
            parser.error("Passwords do not match.")
        try:
            payload = UserCreate(name=args.name, email=args.email, password=first, role=Role.ADMIN)
        except ValidationError:
            parser.error("Provide a valid email, a 2–100 character name and a 12–128 character password.")

    engine = make_engine(Settings().database_url)
    try:
        initialize(engine)
        with Session(engine) as db, db.begin():
            if args.command == "seed-demo":
                inserted = seed_demo(db)
                message = "Demo workspace seeded." if inserted else "Demo workspace already exists."
            elif args.command == "reset-demo":
                reset_demo(db)
                message = "Demo workspace reset."
            else:
                if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
                    raise ValueError("This email is already registered.")
                db.add(User(name=payload.name, email=payload.email, role=payload.role,
                            password_hash=hash_password(payload.password.get_secret_value())))
                message = "Administrator created."
        print(message)
    except ValueError as error:
        parser.error(str(error))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
