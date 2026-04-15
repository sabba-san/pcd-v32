"""
SQLAlchemy User model with role-specific fields.
All role-specific columns are nullable so the same table covers all user types.
"""
import enum
from datetime import datetime, timezone
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


# ── Lidar Defect Models ──────────────────────────────────────────────────────

class DefectStatus(str, enum.Enum):
    REPORTED = 'Reported'
    UNDER_REVIEW = 'Under Review'
    FIXED = 'Fixed'

class DefectPriority(str, enum.Enum):
    URGENT = 'Urgent'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class DefectSeverity(str, enum.Enum):
    CRITICAL = 'Critical'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class Scan(db.Model):
    __tablename__ = 'scans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    model_path = db.Column(db.String(500))  # Path to 3D model file
    created_at = db.Column(db.DateTime, default=db.func.now())

    defects = db.relationship('Defect', backref='scan', lazy=True)

class Defect(db.Model):
    __tablename__ = 'defects'
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    z = db.Column(db.Float, nullable=False)
    element = db.Column(db.String(255))  # Auto-populated from mesh name (non-editable)
    location = db.Column(db.String(100))  # Room/area location (editable dropdown)
    defect_type = db.Column(db.String(50), default='Unknown')  # crack, water damage, structural, finish, electrical, plumbing
    severity = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Critical
    priority = db.Column(db.String(20), default='Medium')  # Urgent, High, Medium, Low
    description = db.Column(db.Text)  # Auto-populated from mesh label (non-editable)
    status = db.Column(db.String(50), default='Reported')  # Reported, Under Review, Fixed
    image_path = db.Column(db.String(500))  # Path to snapshot image
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())
    activities = db.relationship('ActivityLog', backref='defect', lazy=True)

class ActivityLog(db.Model):
    """Track all changes/activities on defects"""
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id'))
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'))
    action = db.Column(db.String(255), nullable=False)  # "updated status", "assigned to", "updated priority"
    old_value = db.Column(db.String(255))  # Previous value
    new_value = db.Column(db.String(255))  # New value
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    scan = db.relationship('Scan', backref='activities')
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
