# __init__.py
import os
from flask import Flask, redirect, url_for
from .extensions import db, login_manager
from .module1.routes import module1
from .module2.routes import module2
from .module3.routes import module3
from .module4.routes import module4
from .auth.routes import auth
from .core_features import core_features


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

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app


# <--- Add this line at the very bottom!
app = create_app()