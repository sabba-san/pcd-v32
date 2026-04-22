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
    profile_picture = db.Column(db.String(500))  # Path or URL to profile picture

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
    unit                   = db.Column(db.String(100))

    # ── Compliance role alias (used by Nabilah module seed logic) ─────────────
    role                   = db.Column(db.String(50))

    # ── Helpers ───────────────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f'<User {self.email} [{self.user_type}]>'

    # Relationships
    defects = db.relationship('Defect', foreign_keys='Defect.user_id', backref='owner', lazy=True)
    assigned_defects = db.relationship('Defect', foreign_keys='Defect.assigned_developer_id', backref='assigned_developer', lazy=True)
    login_accounts = db.relationship('LoginAccount', backref='user', lazy=True)
    audit_entries = db.relationship('AuditLogEntry', backref='user', lazy=True)


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
    completed_date = db.Column(db.Date)
    
    # ── Compliance Module (Nabilah) Fields ───────────────────────────────────
    unit = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Linking defect to homeowner
    assigned_developer_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Linking defect to developer
    reported_date = db.Column(db.DateTime, default=db.func.now())
    urgency = db.Column(db.String(50))
    deadline = db.Column(db.Date)
    remarks = db.Column(db.Text)
    remarks_list = db.relationship('Remark', backref='defect', lazy=True)
    completion_dates = db.relationship('CompletionDate', backref='defect', lazy=True)
    evidence_list = db.relationship('Evidence', backref='defect', lazy=True)
    report_versions = db.relationship('ReportVersion', backref='defect', lazy=True)
    audit_log_entries = db.relationship('AuditLogEntry', backref='defect', lazy=True)

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

# ── Compliance Module Models (Nabilah) ───────────────────────────────────────

class ReportHomeownerProfile(db.Model):
    __tablename__ = 'report_homeowner_profile'
    homeowner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    ic_number = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone_number = db.Column(db.String(100))
    address = db.Column(db.String(255))
    court_location = db.Column(db.String(255))
    state_name = db.Column(db.String(100))
    claim_amount = db.Column(db.String(100))
    item_service = db.Column(db.String(255))
    transaction_date = db.Column(db.Date)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

class ReportRespondentProfile(db.Model):
    __tablename__ = 'report_respondent_profile'
    respondent_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    registration_number = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone_number = db.Column(db.String(100))
    address = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

class ReportClaimRegistry(db.Model):
    __tablename__ = 'report_claim_registry'
    claim_id = db.Column(db.String(64), primary_key=True)
    case_key = db.Column(db.String(255), unique=True, nullable=False)
    case_number = db.Column(db.String(6), nullable=False)
    claim_year = db.Column(db.Integer, nullable=False)
    date_filed = db.Column(db.DateTime, default=db.func.now())
    state = db.Column(db.String(100), nullable=False)
    state_code = db.Column(db.String(20), nullable=False)
    homeowner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    respondent_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


# ── New Supplemental Models (Migrated from Raw SQL) ───────────────────────────

class Remark(db.Model):
    __tablename__ = 'remarks'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(100))  # Kept for compatibility
    remarks = db.Column(db.Text)      # User requested name
    created_at = db.Column(db.DateTime, default=db.func.now())

class CompletionDate(db.Model):
    __tablename__ = 'completion_dates'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id', ondelete='CASCADE'), nullable=False)
    completion_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

class Evidence(db.Model):
    __tablename__ = 'evidence'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id', ondelete='CASCADE'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False) # User requested
    file_type = db.Column(db.String(50))                  # User requested
    filename = db.Column(db.String(255))                 # Legacy compatibility
    uploaded_at = db.Column(db.DateTime, default=db.func.now()) # Legacy compatibility
    created_at = db.Column(db.DateTime, default=db.func.now())   # User requested

class AuditLogEntry(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id', ondelete='SET NULL'))
    action = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    role = db.Column(db.String(50))        # Legacy compatibility
    filename = db.Column(db.String(255))   # Legacy compatibility
    new_status = db.Column(db.String(50))  # Legacy compatibility
    details = db.Column(db.JSON)           # Legacy compatibility
    timestamp = db.Column(db.DateTime, default=db.func.now())

class ReportVersion(db.Model):
    __tablename__ = 'report_versions'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id', ondelete='CASCADE'))
    role = db.Column(db.String(50))          # Legacy compatibility
    version_number = db.Column(db.String(50)) # User requested
    version_no = db.Column(db.String(50))     # Legacy compatibility
    language = db.Column(db.String(20))       # Legacy compatibility
    report_text = db.Column(db.Text)         # Legacy compatibility
    s3_link = db.Column(db.String(500))      # User requested
    generated_at = db.Column(db.DateTime, default=db.func.now()) # Legacy compatibility
    created_at = db.Column(db.DateTime, default=db.func.now())   # User requested

class LoginAccount(db.Model):
    __tablename__ = 'login_accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    username = db.Column(db.String(100), unique=True) # Legacy compatibility
    email = db.Column(db.String(150))                 # User requested
    password = db.Column(db.String(255))              # Legacy compatibility
    password_hash = db.Column(db.String(256))         # User requested
    role = db.Column(db.String(50))                   # Legacy compatibility
    is_active = db.Column(db.Boolean, default=True)   # Legacy compatibility
    created_at = db.Column(db.DateTime, default=db.func.now())
