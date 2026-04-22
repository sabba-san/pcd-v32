# __init__.py
import os
from flask import Flask, redirect, url_for
from sqlalchemy import text
from dotenv import load_dotenv
from .extensions import db, login_manager
from .module1.routes import module1
from .module2.routes import module2
from .module3.routes import module3
from .module4.routes import module4
from .auth.routes import auth
from .core_features import core_features

# Load .env before any app config or AI client access.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # ── Core config ───────────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'postgresql://user:password@flask_db:5432/flaskdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(module1)
    app.register_blueprint(module2)
    app.register_blueprint(module3, url_prefix='/module3')
    app.register_blueprint(module4)
    app.register_blueprint(auth)
    app.register_blueprint(core_features)

    # ── Create DB tables on first run ─────────────────────────────────────────
    with app.app_context():
        from . import models  # noqa: F401 — ensures models are registered before create_all
        db.create_all()
        # ── Safe migrations for new columns (idempotent) ──────────────────────
        for stmt in [
            "ALTER TABLE defects ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE defects ADD COLUMN IF NOT EXISTS verified_by_id INTEGER REFERENCES users(id)",
            "ALTER TABLE defects ADD COLUMN IF NOT EXISTS legal_remarks TEXT",
        ]:
            try:
                db.session.execute(text(stmt))
            except Exception:
                db.session.rollback()
        db.session.commit()

    @app.cli.command("init-db")
    def init_db_command():
        """Initialize the database safely (tables and seed data)."""
        import click
        from .module3.routes import _ensure_module3_tables, _ensure_login_accounts_seeded
        from .module3.report_data import _ensure_report_metadata_tables
        
        click.echo("Creating SQLAlchemy tables...")
        from . import models  # noqa: F401
        db.create_all()
        
        click.echo("Ensuring Module 3 supplemental tables...")
        _ensure_module3_tables()
        
        click.echo("Ensuring report metadata tables...")
        _ensure_report_metadata_tables()
        
        click.echo("Seeding login accounts...")
        _ensure_login_accounts_seeded()

        click.echo("Synchronizing database sequences...")
        db.session.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM users;"))
        db.session.commit()
        
        click.echo("Database initialization complete.")

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app


# <--- Add this line at the very bottom!
app = create_app()
