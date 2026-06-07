"""
Standalone script to seed or reset the admin user for the DLP Advisor platform.

Usage (from project root):
    python create_admin.py

The script will:
    1. Load the Flask app (reads DATABASE_URL from environment or .env).
    2. Check if admin@dlpadvisor.com exists in the users table.
    3. If not found → create a new admin user.
    4. If found → reset the password.
    5. Print a result message.
"""

import sys

# ---------------------------------------------------------------------------
# Configuration — change these before running in production if needed
# ---------------------------------------------------------------------------
ADMIN_EMAIL    = "admin@dlpadvisor.com"
ADMIN_NAME     = "Admin"
ADMIN_USERNAME = "admin"          # legacy login_accounts compatibility
ADMIN_PASSWORD = "Admin@DLP2026!"
ADMIN_ROLE     = "admin"          # stored in both user_type (primary) and role (legacy)

# ---------------------------------------------------------------------------
# Bootstrap Flask and database
# ---------------------------------------------------------------------------
# The app factory reads DATABASE_URL from os.environ / .env automatically.
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    existing = User.query.filter_by(email=ADMIN_EMAIL).first()

    if existing:
        # ── Update password for existing admin ────────────────────────────
        existing.set_password(ADMIN_PASSWORD)
        # Ensure role/type fields are set (harmless if already correct)
        existing.user_type = ADMIN_ROLE
        existing.role      = ADMIN_ROLE
        db.session.commit()
        print(f"[OK] Admin password reset for {ADMIN_EMAIL}")
    else:
        # ── Create brand-new admin user ────────────────────────────────────
        user = User(
            email     = ADMIN_EMAIL,
            full_name = ADMIN_NAME,
            user_type = ADMIN_ROLE,
            role      = ADMIN_ROLE,
        )
        user.set_password(ADMIN_PASSWORD)
        db.session.add(user)
        db.session.commit()
        print(f"[OK] Admin user created: {ADMIN_EMAIL}")

    print(f"[OK] You can now log in at the web app with:")
    print(f"     Email   : {ADMIN_EMAIL}")
    print(f"     Password: {ADMIN_PASSWORD}")
    sys.exit(0)
