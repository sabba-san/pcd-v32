#!/usr/bin/env python3
"""Create an admin user for the DLP Advisor platform."""

import sys
import os
from pathlib import Path

# Load .env to get the DATABASE_URL, then rewrite the Docker hostname
# so we can reach PostgreSQL from the host via Docker's port mapping.
dotenv_path = Path(__file__).resolve().parent / '.env'
if dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

db_url = os.environ.get('DATABASE_URL', '')
if 'flask_db' in db_url:
    db_url = db_url.replace('@flask_db:', '@localhost:')
    os.environ['DATABASE_URL'] = db_url

# Must be set BEFORE importing app, because __init__.py runs load_dotenv
# and calls create_app() at module level.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    admin_email = 'admin@dlpadvisor.com'
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        print(f'Admin user already exists: {existing.email} (id={existing.id})')
        sys.exit(0)

    admin = User(
        user_type='admin',
        role='admin',
        full_name='System Admin',
        email=admin_email,
    )
    admin.set_password('adminpassword123')
    db.session.add(admin)
    db.session.commit()
    print(f'Admin user created: {admin.email} (id={admin.id})')
