"""
SQLAlchemy User model with role-specific fields.
All role-specific columns are nullable so the same table covers all user types.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, login_manager


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    # ── Core fields (required for all roles) ──────────────────────────────────
    id            = db.Column(db.Integer, primary_key=True)
    user_type     = db.Column(db.String(20), nullable=False)   # 'developer' | 'lawyer' | 'homeowner'
    full_name     = db.Column(db.String(150), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # ── Developer / Housing-Developer fields ──────────────────────────────────
    company_name         = db.Column(db.String(150))
    ssm_registration     = db.Column(db.String(50))
    company_address      = db.Column(db.Text)
    phone_number         = db.Column(db.String(30))   # shared with homeowner
    fax_email            = db.Column(db.String(150))
    representative_name  = db.Column(db.String(150))
    representative_nric  = db.Column(db.String(20))

    # ── Lawyer fields ─────────────────────────────────────────────────────────
    law_firm_name  = db.Column(db.String(150))
    bar_council_id = db.Column(db.String(50))

    # ── Homeowner fields ──────────────────────────────────────────────────────
    housing_project        = db.Column(db.String(150))
    ic_number              = db.Column(db.String(20))
    correspondence_address = db.Column(db.Text)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f'<User {self.email} [{self.user_type}]>'


# Flask-Login user loader ─────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))
