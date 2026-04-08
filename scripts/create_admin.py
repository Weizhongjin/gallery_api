#!/usr/bin/env python3
"""Create the first admin user.

Usage (from gallery-api/ directory):
    python scripts/create_admin.py --email admin@example.com --name "Admin" --password mypassword
"""
import argparse
import sys
import os

# Allow running from gallery-api/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.auth.models import User, UserRole
from app.auth.service import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--name", required=True, help="Admin display name")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--company", default=None, help="Company name (optional)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == args.email).first()
        if existing:
            print(f"Error: User {args.email} already exists (role={existing.role})")
            sys.exit(1)

        user = User(
            email=args.email,
            name=args.name,
            password_hash=hash_password(args.password),
            role=UserRole.admin,
            company=args.company,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created admin user: {args.email} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
