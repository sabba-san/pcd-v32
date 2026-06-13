from flask_login import login_required, current_user
from flask import (
    Blueprint,
    render_template,
    send_file,
    request,
    current_app,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
    abort,
)

try:
    from .config_mappings import (
        STATUS_NORMALISE,
        STATUS_TRANSLATION,
        PRIORITY_TRANSLATION,
    )
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from config_mappings import (
        STATUS_NORMALISE,
        STATUS_TRANSLATION,
        PRIORITY_TRANSLATION,
    )

# reportlab is used exclusively in services/pdf_service.py — no direct
# reportlab imports are needed here.

from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import re
import hashlib
import base64


def get_connection():
    from ..extensions import db
    return db.engine.raw_connection()

from sqlalchemy import text

# --------------------------------
# IMPORT DATA & SERVICES
# --------------------------------
try:
    from .config_pdf_labels import PDF_LABELS
    from .report_data import (
        build_report_data,
        get_homeowner_claimants,
        validate_report_requirements,
    )
    from .report_generator import generate_ai_report
    from .services.pdf_service import generate_tribunal_pdf
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from config_pdf_labels import PDF_LABELS
    from report_data import (
        build_report_data,
        get_homeowner_claimants,
        validate_report_requirements,
    )
    from report_generator import generate_ai_report
    from services.pdf_service import generate_tribunal_pdf
try:
    from .ai_translate_cached import (
        translate_defects_cached,
        translate_report_cached,
        translate_remark_cached,
    )
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from ai_translate_cached import (
        translate_defects_cached,
        translate_report_cached,
        translate_remark_cached,
    )

from ..extensions import db
from ..models import User

SUPPORT_CONTACT = "1800-700-321 | support@dlp-project.edu.my"
AUTO_CLOSE_DAYS = int(os.getenv("AUTO_CLOSE_DAYS", "14"))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "120"))

STATE_COURT_MAP = {
    "Johor": {
        "tribunal_branches": ["Johor Bahru", "Batu Pahat", "Muar"],
        "general_locations": ["Kluang", "Segamat"],
    },
    "Kedah": {
        "tribunal_branches": ["Alor Setar", "Sungai Petani"],
        "general_locations": ["Kulim", "Langkawi"],
    },
    "Kelantan": {
        "tribunal_branches": ["Kota Bharu", "Pasir Mas"],
        "general_locations": ["Tumpat", "Tanah Merah"],
    },
    "Melaka": {
        "tribunal_branches": ["Melaka Tengah", "Alor Gajah"],
        "general_locations": ["Jasin"],
    },
    "Negeri Sembilan": {
        "tribunal_branches": ["Seremban", "Port Dickson"],
        "general_locations": ["Tampin", "Kuala Pilah"],
    },
    "Pahang": {
        "tribunal_branches": ["Kuantan", "Temerloh"],
        "general_locations": ["Pekan", "Bentong", "Raub"],
    },
    "Perak": {
        "tribunal_branches": ["Ipoh", "Taiping", "Kuala Kangsar"],
        "general_locations": ["Teluk Intan", "Sitiawan", "Parit Buntar"],
    },
    "Perlis": {
        "tribunal_branches": ["Kangar"],
        "general_locations": [],
    },
    "Pulau Pinang": {
        "tribunal_branches": ["George Town", "Seberang Jaya"],
        "general_locations": ["Bukit Mertajam"],
    },
    "Sabah": {
        "tribunal_branches": ["Kota Kinabalu", "Sandakan", "Tawau"],
        "general_locations": ["Keningau", "Beaufort", "Lahad Datu"],
    },
    "Sarawak": {
        "tribunal_branches": ["Kuching", "Sibu", "Miri"],
        "general_locations": ["Bintulu", "Sri Aman", "Limbang"],
    },
    "Selangor": {
        "tribunal_branches": ["Shah Alam", "Petaling Jaya", "Klang"],
        "general_locations": ["Kajang", "Selayang"],
    },
    "Terengganu": {
        "tribunal_branches": ["Kuala Terengganu", "Dungun"],
        "general_locations": ["Kemaman", "Besut"],
    },
    "Kuala Lumpur": {
        "tribunal_branches": ["Kuala Lumpur", "Jalan Duta"],
        "general_locations": ["Setapak"],
    },
    "W.P. Kuala Lumpur": {
        "tribunal_branches": ["Kuala Lumpur", "Jalan Duta"],
        "general_locations": ["Setapak"],
    },
    "Putrajaya": {
        "tribunal_branches": ["Putrajaya"],
        "general_locations": [],
    },
    "W.P. Putrajaya": {
        "tribunal_branches": ["Putrajaya"],
        "general_locations": [],
    },
    "Labuan": {
        "tribunal_branches": ["Labuan"],
        "general_locations": [],
    },
    "W.P. Labuan": {
        "tribunal_branches": ["Labuan"],
        "general_locations": [],
    },
}

ITEM_SERVICE_TRANSLATIONS = {
    "Defect Repair During DLP": {
        "en": "Defect Repair During DLP",
        "ms": "Pembaikan Kecacatan Dalam Tempoh DLP",
    },
    "Home Repair Works": {
        "en": "Home Repair Works",
        "ms": "Kerja Pembaikan Rumah",
    },
    "Post-Handover Defect Rectification": {
        "en": "Post-Handover Defect Rectification",
        "ms": "Kerja Pembetulan Kecacatan Selepas Serahan Milikan",
    },
    "Others": {
        "en": "Others",
        "ms": "Lain-lain",
    },
}

ITEM_SERVICE_ALIASES = {
    "defect repair during dlp": "Defect Repair During DLP",
    "defect repairs during dlp period": "Defect Repair During DLP",
    "pembaikan kecacatan dalam tempoh dlp": "Defect Repair During DLP",
    "home repair works": "Home Repair Works",
    "kerja pembaikan rumah": "Home Repair Works",
    "post-handover defect rectification": "Post-Handover Defect Rectification",
    "defect repair after handover": "Post-Handover Defect Rectification",
    "defect repair during dlp": "Defect Repair During DLP",
    "lain-lain": "Others",
    "others": "Others",
}


def _default_item_service():
    return "Defect Repair During DLP"


def _normalise_item_service(value):
    raw = (value or "").strip()
    if not raw:
        return _default_item_service()

    if raw in ITEM_SERVICE_TRANSLATIONS:
        return raw

    return ITEM_SERVICE_ALIASES.get(raw.lower(), _default_item_service())


def _item_service_for_language(value, language):
    canonical = _normalise_item_service(value)
    language_key = "ms" if language == "ms" else "en"
    return ITEM_SERVICE_TRANSLATIONS.get(canonical, ITEM_SERVICE_TRANSLATIONS[_default_item_service()])[language_key]


def _get_court_locations_for_state(state_name):
    state_entry = STATE_COURT_MAP.get(state_name) or {}
    tribunal_branches = state_entry.get("tribunal_branches") or []
    general_locations = state_entry.get("general_locations") or []
    return tribunal_branches + [location for location in general_locations if location not in tribunal_branches]

LOGIN_ACCOUNT_SEED = [
    {
        "username": "homeowner",
        "password": "home123",
        "role": "Homeowner",
        "full_name": "Homeowner A",
        "unit": "A-01-01",
        "email": "homeowner1@demo.local",
    },
    {
        "username": "developer",
        "password": "dev123",
        "role": "Developer",
        "full_name": "Developer A",
        "unit": "Developer Office",
        "email": "developer1@demo.local",
    },
    {
        "username": "legal",
        "password": "legal123",
        "role": "Legal",
        "full_name": "Legal A",
        "unit": "Legal Office",
        "email": "legal1@demo.local",
    },
    {
        "username": "homeowner2",
        "password": "home223",
        "role": "Homeowner",
        "full_name": "Homeowner B",
        "unit": "A-02-02",
        "email": "homeowner2@demo.local",
    },
]

# --------------------------------
# BLUEPRINT
# --------------------------------
module3 = Blueprint("module3", __name__)
routes = module3
bp = routes

# --------------------------------
# IMAGE UPLOAD CONFIG
# --------------------------------
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'tif', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _now_app_timezone():
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:
        # Fallback for environments without tzdata (common in slim containers).
        if APP_TIMEZONE == "Asia/Kuala_Lumpur":
            return datetime.now(timezone.utc) + timedelta(hours=8)
        return datetime.now()


# NOTE: The three helpers below (VALID_IMAGE_EXTENSIONS, _is_valid_image_path,
# _resolve_evidence_image_path) are also defined in services/pdf_service.py.
# They are kept here because they are called at multiple sites within this file
# (e.g. build_closed_appendix_lines calls at lines ~1607, ~1622).
# Future consolidation: import them from pdf_service and remove these copies.
VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.gif', '.bmp', '.webp'}

def _is_valid_image_path(path):
    """Return True only if the path has a recognised image extension."""
    if not path:
        return False
    ext = os.path.splitext(str(path))[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS

def _resolve_evidence_image_path(evidence_dir, defect_id, evidence_filename=None):
    """Resolve an absolute path to an evidence image.

    Returns None if no file can be found OR the resolved file does not carry a
    recognised image extension (guards against placeholder/junk filenames like
    'gambar' being treated as valid images).
    """
    if not evidence_dir or not os.path.isdir(evidence_dir):
        return None

    # Only proceed if we have a real filename (not literals like '-' or 'gambar')
    candidate_name = (evidence_filename or "").strip()

    # 1) Try exact filename from metadata — must have a valid image extension.
    if candidate_name and candidate_name not in ("-", "gambar", "image") and _is_valid_image_path(candidate_name):
        direct_candidate = os.path.join(evidence_dir, os.path.basename(candidate_name))
        if os.path.exists(direct_candidate):
            return direct_candidate

        # Case-insensitive fallback
        basename_lower = os.path.basename(candidate_name).lower()
        for fname in os.listdir(evidence_dir):
            if fname.lower() == basename_lower:
                full_path = os.path.join(evidence_dir, fname)
                if os.path.isfile(full_path) and _is_valid_image_path(full_path):
                    return full_path

    # 2) Legacy defect_<id>.ext naming — only when we have a valid filename metadata
    #    (prevents matching pre-seeded placeholder files when no evidence was uploaded).
    if candidate_name and candidate_name not in ("-", "gambar", "image") and _is_valid_image_path(candidate_name):
        prefix = f"defect_{defect_id}.".lower()
        for fname in os.listdir(evidence_dir):
            if fname.lower().startswith(prefix) and _is_valid_image_path(fname):
                full_path = os.path.join(evidence_dir, fname)
                if os.path.isfile(full_path):
                    return full_path

    return None


def _current_role():
    return current_user.user_type if current_user.is_authenticated else None


def _current_role_key():
    role = _current_role()
    return role.lower() if isinstance(role, str) else None


def _current_actor_name():
    if current_user.is_authenticated:
        return getattr(current_user, "full_name", None) or getattr(current_user, "email", None) or f"user:{current_user.id}"
    return ""


def _current_user_id():
    return current_user.id if current_user.is_authenticated else None


def _append_audit_event(action, role=None, defect_id=None, filename=None, new_status=None, details=None):
    audit = load_audit()
    audit.append(
        {
            "action": action,
            "role": role,
            "defect_id": defect_id,
            "filename": filename,
            "new_status": new_status,
            "timestamp": _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S"),
            "details": details or {},
        }
    )
    save_audit(audit)


def _is_password_hash(value):
    if not value:
        return False
    return value.startswith("pbkdf2:") or value.startswith("scrypt:")

def _ensure_module3_tables():
    """
    Ensure Module 3 supplemental tables and columns exist.
    Tables (remarks, completion_dates, evidence, audit_log, report_versions, login_accounts)
    are now managed by SQLAlchemy models in models.py.
    """
    from ..extensions import db
    
    # db.create_all() in init-db handles supplemental tables now.
    
    # Safely add columns to defects table if they are missing (backward compatibility)
    try:
        db.session.execute(text("ALTER TABLE defects ADD COLUMN IF NOT EXISTS remarks TEXT"))
    except Exception as e:
        current_app.logger.debug(f"Note: remarks column might already exist: {e}")
    
    # assigned_developer_id (for defect routing)
    try:
        db.session.execute(text("ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_developer_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    except Exception as e:
        current_app.logger.debug(f"Note: assigned_developer_id column might already exist: {e}")

    try:
        db.session.execute(text("ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_lawyer_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    except Exception as e:
        current_app.logger.debug(f"Note: assigned_lawyer_id column might already exist: {e}")

    # Ensure completion_dates.defect_id has a unique constraint (required for ON CONFLICT upsert).
    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_completion_dates_defect_id ON completion_dates (defect_id)"
        ))
    except Exception as e:
        current_app.logger.debug(f"Note: completion_dates unique index: {e}")

    db.session.commit()


def _ensure_login_accounts_seeded():
    """
    Seed the login_accounts table with initial data.
    Table creation is now managed by SQLAlchemy models.
    """
    from ..extensions import db
    try:
        db.session.execute(text(
            "DELETE FROM login_accounts WHERE LOWER(username) IN ('developer2', 'legal2')"
        ))

        role_mapping = {
            "Homeowner": "homeowner",
            "Developer": "developer",
            "Legal": "lawyer",
            "Admin": "admin"
        }

        for acc in LOGIN_ACCOUNT_SEED:
            result = db.session.execute(text(
                """
                SELECT id
                FROM users
                WHERE LOWER(full_name) = LOWER(:full_name) AND role = :role
                LIMIT 1
                """
            ), {"full_name": acc["full_name"], "role": acc["role"]})
            user_row = result.fetchone()

            if user_row:
                mapped_user_id = user_row[0]
            else:
                user_type = role_mapping.get(acc["role"], "homeowner")
                pwd_hash = generate_password_hash(acc["password"])
                
                insert_res = db.session.execute(text(
                    """
                    INSERT INTO users (full_name, unit, role, email, user_type, password_hash)
                    VALUES (:full_name, :unit, :role, :email, :user_type, :password_hash)
                    RETURNING id
                    """
                ), {
                    "full_name": acc["full_name"],
                    "unit": acc["unit"],
                    "role": acc["role"],
                    "email": acc["email"],
                    "user_type": user_type,
                    "password_hash": pwd_hash
                })
                mapped_user_id = insert_res.fetchone()[0]

            db.session.execute(text(
                """
                INSERT INTO login_accounts (username, password, role, user_id, is_active, email, password_hash)
                VALUES (:username, :password, :role, :user_id, TRUE, :email, :password_hash)
                ON CONFLICT (username) DO UPDATE
                SET role = EXCLUDED.role,
                    user_id = COALESCE(login_accounts.user_id, EXCLUDED.user_id),
                    password = EXCLUDED.password,
                    email = EXCLUDED.email,
                    password_hash = EXCLUDED.password_hash
                """
            ), {
                "username": acc["username"],
                "password": acc["password"],
                "role": acc["role"],
                "user_id": mapped_user_id,
                "email": acc["email"],
                "password_hash": generate_password_hash(acc["password"])
            })

        # Ensure admin account
        admin_pwd_hash = generate_password_hash("admin123")
        db.session.execute(text(
            """
            INSERT INTO login_accounts (username, password, role, user_id, is_active, email, password_hash)
            VALUES (:username, :password, :role, :user_id, TRUE, :email, :password_hash)
            ON CONFLICT (username) DO NOTHING
            """
        ), {
            "username": "admin",
            "password": admin_pwd_hash,
            "role": "Admin",
            "user_id": None,
            "email": "admin@demo.local",
            "password_hash": admin_pwd_hash
        })

        # Auto-upgrade any legacy plaintext passwords already stored in DB.
        legacy_res = db.session.execute(text("SELECT username, password FROM login_accounts"))
        for username, stored_password in legacy_res.fetchall():
            if stored_password and not _is_password_hash(stored_password):
                db.session.execute(text(
                    "UPDATE login_accounts SET password = :password WHERE username = :username"
                ), {"password": generate_password_hash(stored_password), "username": username})

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


def _get_login_account(username, password, selected_role):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT username, role, user_id, password
            FROM login_accounts
            WHERE LOWER(username) = LOWER(%s)
              AND LOWER(role) = LOWER(%s)
              AND is_active = TRUE
            LIMIT 1
            """,
            (username, selected_role),
        )
        row = cur.fetchone()
        if not row:
            return None

        stored_password = row[3] or ""
        password_valid = False

        if _is_password_hash(stored_password):
            password_valid = check_password_hash(stored_password, password)

        if not password_valid:
            return None

        return {
            "username": row[0],
            "role": row[1],
            "user_id": row[2],
        }
    finally:
        cur.close()
        conn.close()


# --------------------------------
# DATABASE HELPERS
# --------------------------------

def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def get_current_user():
    conn = get_connection()
    cur = conn.cursor()
    try:
        user_id = _current_user_id()
        cur.execute(
            "SELECT id, full_name, unit, role, profile_picture FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"name": "User", "unit": "Unknown", "profile_picture": None}

        display_name = row[1]
        if row[3] == "Homeowner":
            cur.execute(
                "SELECT name FROM report_homeowner_profile WHERE homeowner_id = %s",
                (user_id,),
            )
            homeowner_profile = cur.fetchone()
            if homeowner_profile and homeowner_profile[0]:
                display_name = homeowner_profile[0]

        return {
            "name": display_name,
            "unit": row[2] or "",
            "profile_picture": row[4]
        }
    finally:
        cur.close()
        conn.close()


def get_homeowner_claim_details(user_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT court_location, state_name, item_service, transaction_date, claim_amount, address
            FROM report_homeowner_profile
            WHERE homeowner_id = %s
            """,
            (user_id,),
        )
        homeowner_row = cur.fetchone()

        cur.execute(
            """
            SELECT assigned_lawyer_id
            FROM defects
            WHERE user_id = %s
              AND assigned_lawyer_id IS NOT NULL
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_id,),
        )
        lawyer_row = cur.fetchone()

        cur.execute("ALTER TABLE report_respondent_profile ADD COLUMN IF NOT EXISTS homeowner_id INTEGER")
        cur.execute(
            """
            SELECT company_name, registration_number, email, phone_number, address
            FROM report_respondent_profile
            WHERE homeowner_id = %s
            ORDER BY updated_at DESC, respondent_id ASC
            LIMIT 1
            """,
            (user_id,),
        )
        respondent_row = cur.fetchone()

        result = {
            "homeowner_address": "",
            "court_location": "",
            "state_name": "",
            "item_service": _default_item_service(),
            "transaction_date": "",
            "claim_amount": "",
            "respondent_company_name": "",
            "respondent_registration_number": "",
            "respondent_email": "",
            "respondent_phone_number": "",
            "respondent_address": "",
            "assigned_lawyer_id": "",
        }

        if homeowner_row:
            result.update(
                {
                    "homeowner_address": homeowner_row[5] or "",
                    "court_location": homeowner_row[0] or "",
                    "state_name": homeowner_row[1] or "",
                    "item_service": _normalise_item_service(homeowner_row[2]),
                    "transaction_date": homeowner_row[3].strftime("%Y-%m-%d") if homeowner_row[3] else "",
                    "claim_amount": str(homeowner_row[4]) if homeowner_row[4] is not None else "",
                }
            )

        if respondent_row:
            result.update(
                {
                    "respondent_company_name": respondent_row[0] or "",
                    "respondent_registration_number": respondent_row[1] or "",
                    "respondent_email": respondent_row[2] or "",
                    "respondent_phone_number": respondent_row[3] or "",
                    "respondent_address": respondent_row[4] or "",
                }
            )

        if lawyer_row and lawyer_row[0] is not None:
            result["assigned_lawyer_id"] = str(lawyer_row[0])

        return result
    finally:
        cur.close()
        conn.close()


def _get_registered_developers():
    """Fetch all users with the role 'Developer' to populate the dropdown."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, company_name, full_name, email, phone_number, company_address, ssm_registration
            FROM users
            WHERE role = 'Developer' OR user_type = 'developer'
            ORDER BY company_name ASC, full_name ASC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "company_name": row[1] or row[2] or f"Dev #{row[0]}",
                "email": row[3] or "",
                "phone_number": row[4] or "",
                "address": row[5] or "",
                "registration_number": row[6] or "",
            }
            for row in rows
        ]
    finally:
        cur.close()
        conn.close()


def _get_registered_lawyers():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, law_firm_name, full_name, email
            FROM users
            WHERE user_type = 'lawyer' OR role = 'Legal'
            ORDER BY COALESCE(NULLIF(law_firm_name, ''), full_name) ASC, full_name ASC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "law_firm_name": row[1] or "",
                "full_name": row[2] or "",
                "email": row[3] or "",
                "display_name": row[1] or row[2] or f"Lawyer #{row[0]}",
            }
            for row in rows
        ]
    finally:
        cur.close()
        conn.close()


def _lawyer_has_access_to_defect(defect_id, lawyer_id=None):
    if lawyer_id is None:
        lawyer_id = _current_user_id()
    if not lawyer_id:
        return False

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM defects
            WHERE id = %s
              AND assigned_lawyer_id = %s
            LIMIT 1
            """,
            (int(defect_id), int(lawyer_id)),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def _assert_legal_defect_access(defect_id):
    if _current_role_key() not in {"lawyer", "legal"}:
        return None
    if _lawyer_has_access_to_defect(defect_id):
        return None
    return jsonify({"error": "Forbidden"}), 403


def _get_allowed_claimant_ids_for_legal():
    lawyer_id = _current_user_id()
    if not lawyer_id:
        return set()
    return {
        item["homeowner_id"]
        for item in get_homeowner_claimants(lawyer_user_id=lawyer_id)
        if item.get("homeowner_id") is not None
    }


def _resolve_claimant_user_id(role, claimant_user_id, defects):
    if role == "Homeowner":
        return _current_user_id()

    if role == "Legal":
        allowed_claimant_ids = _get_allowed_claimant_ids_for_legal()
        if claimant_user_id is not None:
            return claimant_user_id if claimant_user_id in allowed_claimant_ids else None

        derived_ids = [
            d.get("user_id")
            for d in defects
            if d.get("user_id") in allowed_claimant_ids
        ]
        if derived_ids:
            return derived_ids[0]

        allowed_claimants = get_homeowner_claimants(lawyer_user_id=_current_user_id())
        return allowed_claimants[0]["homeowner_id"] if allowed_claimants else None

    if defects and defects[0].get("user_id"):
        return defects[0].get("user_id")

    if claimant_user_id is not None:
        return claimant_user_id

    claimants = get_homeowner_claimants()
    return claimants[0]["homeowner_id"] if claimants else None


def calculate_hda_compliance(reported_date, completed_date, status):
    if not reported_date:
        return True

    try:
        reported_date_obj = datetime.strptime(str(reported_date), "%Y-%m-%d")
    except Exception:
        return True

    if status not in {"Completed", "Closed", "Archived"} or not completed_date:
        return False

    try:
        completed_date_obj = datetime.strptime(str(completed_date), "%Y-%m-%d")
    except Exception:
        return False

    days_taken = (completed_date_obj - reported_date_obj).days
    return days_taken <= 30


def calculate_overdue(deadline, completed_date, status):
    if not deadline:
        return False

    try:
        deadline_date = datetime.strptime(str(deadline), "%Y-%m-%d")
    except Exception:
        return False

    if status in {"Completed", "Closed", "Archived"} and completed_date:
        try:
            completed_date_obj = datetime.strptime(str(completed_date), "%Y-%m-%d")
            return completed_date_obj > deadline_date
        except Exception:
            return False

    if status not in {"Completed", "Closed", "Archived"}:
        return _now_app_timezone().date() > deadline_date.date()

    return False


def calculate_days_to_complete(reported_date, completed_date):
    if not reported_date or not completed_date:
        return None

    try:
        reported_date_obj = datetime.strptime(str(reported_date)[:10], "%Y-%m-%d").date()
        completed_date_obj = datetime.strptime(str(completed_date)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

    return max((completed_date_obj - reported_date_obj).days, 0)


def backfill_missing_deadlines():
    """Populate deadline for legacy defects using reported_date + 30 days."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE defects
            SET deadline = (reported_date::date + INTERVAL '30 days')::date
            WHERE deadline IS NULL
              AND reported_date IS NOT NULL
            """
        )
        updated = cur.rowcount or 0
        conn.commit()
        return updated
    finally:
        cur.close()
        conn.close()


def is_auto_closed(status, completed_date):
    if status in {"Closed", "Archived"}:
        return True

    if status != "Completed" or not completed_date:
        return False

    try:
        completed_dt = datetime.strptime(str(completed_date)[:10], "%Y-%m-%d").date()
    except Exception:
        return False

    cutoff = _now_app_timezone().date() - timedelta(days=AUTO_CLOSE_DAYS)
    return completed_dt <= cutoff


def calculate_stats(defects):
    return {
        "total": len(defects),
        "pending": sum(1 for d in defects if d["status"] in ["Pending", "Reported"]),
        "in_progress": sum(1 for d in defects if d["status"] in ["In Progress", "WIP"]),
        "delayed": sum(1 for d in defects if d["status"] == "Delayed"),
        "overdue": sum(1 for d in defects if d.get("is_overdue")),
        "completed": sum(1 for d in defects if d["status"] == "Completed" and not d.get("closed")),
        "closed": sum(1 for d in defects if d.get("closed")),
        
        # Developer-specific groupings (Job Sheet view)
        "pending_count": sum(1 for d in defects if d["status"] in ["Reported", "Pending", "Delayed"]),
        "wip_count":     sum(1 for d in defects if d["status"] in ["In Progress", "WIP"]),
        "done_count":    sum(1 for d in defects if d["status"] in ["Completed", "Done", "Fixed", "Resolved"]),

        "hda_non_compliant": sum(1 for d in defects if d.get("hda_compliant") is False),
        "critical": sum(1 for d in defects if d.get("urgency") == "High"),
    }


def build_case_key(role, user_id, defects):
    payload = {
        "role": role,
        "user_id": user_id,
        "defects": [
            {
                "id": d.get("id"),
                "unit": d.get("unit"),
                "desc": d.get("desc"),
                "status": d.get("status"),
                "reported_date": d.get("reported_date"),
                "deadline": d.get("deadline"),
                "completed_date": d.get("completed_date"),
            }
            for d in defects
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def auto_close_completed_cases(trigger_role=None):
    """Automatically close cases that stayed completed beyond the configured window."""
    cutoff_date = _now_app_timezone().date() - timedelta(days=AUTO_CLOSE_DAYS)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, completed_date
            FROM defects
            WHERE status = 'Completed'
              AND completed_date IS NOT NULL
              AND completed_date <= %s
            """,
            (cutoff_date,),
        )
        candidates = cur.fetchall()
        if not candidates:
            return 0

        logged_count = 0
        for defect_id, completed_date in candidates:
            cur.execute(
                """
                SELECT 1
                FROM audit_log
                WHERE action = 'Case Auto Closed'
                  AND defect_id = %s
                LIMIT 1
                """,
                (defect_id,),
            )
            if cur.fetchone():
                continue

            _append_audit_event(
                action="Case Auto Closed",
                role="System",
                defect_id=str(defect_id),
                new_status="Completed",
                details={
                    "triggered_by_role": trigger_role,
                    "auto_close_days": AUTO_CLOSE_DAYS,
                    "completed_date": _to_iso(completed_date),
                },
            )
            logged_count += 1

        return logged_count
    finally:
        cur.close()
        conn.close()


def get_defects_for_role(role):
    conn = get_connection()
    cur = conn.cursor()
    try:
        if role == "Homeowner":
            user_id = _current_user_id()
            cur.execute(
                """
                SELECT d.id, d.unit, d.description, d.reported_date, d.status, d.completed_date,
                       d.user_id, d.urgency, d.deadline, d.remarks,
                       COALESCE(d.element, '') AS element, COALESCE(d.location, '') AS location,
                       COALESCE(s.name, '') AS scan_name,
                       d.scan_id,
                       COALESCE(d.image_path, '') AS image_path,
                       COALESCE(u.ic_number, '') AS ic_number
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
                LEFT JOIN users u ON d.user_id = u.id
                WHERE d.user_id = %s
                ORDER BY d.id
                """,
                (user_id,)
            )
        elif role == "Legal":
            user_id = _current_user_id()
            cur.execute(
                """
                SELECT d.id, d.unit, d.description, d.reported_date, d.status, d.completed_date,
                       d.user_id, d.urgency, d.deadline, d.remarks,
                       COALESCE(d.element, '') AS element, COALESCE(d.location, '') AS location,
                       COALESCE(s.name, '') AS scan_name,
                       d.scan_id,
                       COALESCE(d.image_path, '') AS image_path,
                       COALESCE(u.ic_number, '') AS ic_number
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
                LEFT JOIN users u ON d.user_id = u.id
                WHERE d.assigned_lawyer_id = %s
                ORDER BY d.id
                """,
                (user_id,)
            )
        elif role == "Developer":
            user_id = _current_user_id()
            cur.execute(
                """
                SELECT d.id, d.unit, d.description, d.reported_date, d.status, d.completed_date,
                       d.user_id, d.urgency, d.deadline, d.remarks,
                       COALESCE(d.element, '') AS element, COALESCE(d.location, '') AS location,
                       COALESCE(s.name, '') AS scan_name,
                       d.scan_id,
                       COALESCE(d.image_path, '') AS image_path,
                       COALESCE(u.ic_number, '') AS ic_number
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
                LEFT JOIN users u ON d.user_id = u.id
                WHERE d.assigned_developer_id = %s
                ORDER BY d.id
                """,
                (user_id,)
            )
        else:
            cur.execute(
                """
                SELECT d.id, d.unit, d.description, d.reported_date, d.status, d.completed_date,
                       d.user_id, d.urgency, d.deadline, d.remarks,
                       COALESCE(d.element, '') AS element, COALESCE(d.location, '') AS location,
                       COALESCE(s.name, '') AS scan_name,
                       d.scan_id,
                       COALESCE(d.image_path, '') AS image_path,
                       COALESCE(u.ic_number, '') AS ic_number
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
                LEFT JOIN users u ON d.user_id = u.id
                ORDER BY d.id
                """
            )

        defects = []
        for row in cur.fetchall():
            element   = row[10] or ''
            location  = row[11] or ''
            scan_name = row[12] or ''
            scan_id = row[13]
            image_path = row[14] or ''
            ic_number  = row[15] or ''
            raw_unit  = row[1]
            # project_name: explicit unit first, then scan name (taman), then location/element
            project_name = (
                raw_unit
                or scan_name
                or location
                or (element[:30] if element else None)
                or None
            )
            defect = {
                "id":             row[0],
                "unit":           project_name,        # kept as "unit" for JS compat
                "project_name":   project_name,        # explicit alias for templates
                "scan_name":      scan_name,
                "desc":           row[2],
                "reported_date":  _to_iso(row[3]),
                "status":         row[4] or "Reported",
                "completed_date": _to_iso(row[5]),
                "user_id":        row[6],
                "urgency":        row[7],
                "deadline":       _to_iso(row[8]),
                "remarks":        row[9] or "",
                "element":        element,
                "location":       location,
                "scan_id":        scan_id,
                "image_path":     image_path,
                "image_url":      url_for('module2.serve_defect_image', defect_id=row[0]) if image_path else "",
                "ic_number":      ic_number,
            }

            defect["hda_compliant"] = calculate_hda_compliance(
                defect["reported_date"],
                defect.get("completed_date"),
                defect["status"],
            )
            defect["is_overdue"] = calculate_overdue(
                defect["deadline"],
                defect.get("completed_date"),
                defect["status"],
            )
            defect["closed"] = is_auto_closed(defect["status"], defect.get("completed_date"))
            defect["display_status"] = "Closed" if defect["closed"] else defect["status"]
            defects.append(defect)

        return defects
    finally:
        cur.close()
        conn.close()


def _normalise_project_filter_value(value):
    text = str(value or "").strip()
    if text.lower() in {"", "all", "all projects"}:
        return ""
    return text


def filter_defects_by_project(defects, project_filter):
    normalized_filter = _normalise_project_filter_value(project_filter)
    if not normalized_filter:
        return defects

    target = normalized_filter.casefold()
    filtered = []
    for defect in defects:
        candidates = [
            defect.get("project_name"),
            defect.get("scan_name"),
            defect.get("unit"),
        ]
        if any(str(candidate or "").strip().casefold() == target for candidate in candidates):
            filtered.append(defect)
    return filtered

def load_remarks():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT ON (defect_id) defect_id, remarks
            FROM remarks
            ORDER BY defect_id, created_at DESC
            """
        )
        return {str(defect_id): remarks for defect_id, remarks in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

def save_remarks(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        current = load_remarks()
        for defect_id, remark in data.items():
            if current.get(str(defect_id)) == remark:
                continue
            cur.execute(
                "INSERT INTO remarks (defect_id, role, remarks) VALUES (%s, %s, %s)",
                (int(defect_id), "Homeowner", remark),
            )
            cur.execute(
                "UPDATE defects SET remarks = %s WHERE id = %s",
                (remark, int(defect_id)),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def load_status():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, status FROM defects")
        return {str(defect_id): status for defect_id, status in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

def save_status(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for defect_id, status in data.items():
            cur.execute(
                "UPDATE defects SET status = %s WHERE id = %s",
                (status, int(defect_id)),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def load_completion_dates():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT defect_id, completion_date FROM completion_dates")
        return {str(defect_id): _to_iso(completion_date) for defect_id, completion_date in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

def save_completion_dates(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("TRUNCATE TABLE completion_dates")
        for defect_id, completed_date in data.items():
            cur.execute(
                "INSERT INTO completion_dates (defect_id, completion_date) VALUES (%s, %s)",
                (int(defect_id), completed_date),
            )
            cur.execute(
                "UPDATE defects SET completed_date = %s WHERE id = %s",
                (completed_date, int(defect_id)),
            )
        cur.execute(
            "UPDATE defects SET completed_date = NULL WHERE id NOT IN (SELECT defect_id FROM completion_dates)"
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def load_versions():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT role, version_no, generated_at, language, report_text FROM report_versions ORDER BY role, version_no"
        )
        versions = {}
        for role, version_no, generated_at, language, report_text in cur.fetchall():
            versions.setdefault(role, []).append(
                {
                    "version": version_no,
                    "generated_at": str(generated_at),
                    "language": language,
                    "report_text": report_text,
                }
            )
        return versions
    finally:
        cur.close()
        conn.close()

def save_versions(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for role, versions in data.items():
            for v in versions:
                version_no = str(v.get("version"))
                cur.execute(
                    "SELECT 1 FROM report_versions WHERE role = %s AND version_no = %s LIMIT 1",
                    (role, version_no),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    """
                    INSERT INTO report_versions (role, language, version_no, report_text, generated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        role,
                        v.get("language", "ms"),
                        version_no,
                        v.get("report_text", ""),
                        v.get("generated_at", _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S")),
                    ),
                )
        conn.commit()
    finally:
        cur.close()
        conn.close()

# AUDIT LOG FUNCTIONS
def load_audit():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT action, role, defect_id, filename, new_status, timestamp, details FROM audit_log ORDER BY id"
        )
        audit_rows = []
        for action, role, defect_id, filename, new_status, timestamp, details in cur.fetchall():
            row = {
                "action": action,
                "role": role,
                "defect_id": defect_id,
                "filename": filename,
                "new_status": new_status,
                "timestamp": str(timestamp),
            }
            if details:
                row["details"] = details
            audit_rows.append(row)
        return audit_rows
    finally:
        cur.close()
        conn.close()


def get_audit_filter_options():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT role FROM audit_log WHERE role IS NOT NULL AND role <> '' ORDER BY role"
        )
        roles = [row[0] for row in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT action FROM audit_log WHERE action IS NOT NULL AND action <> '' ORDER BY action"
        )
        actions = [row[0] for row in cur.fetchall()]
        return roles, actions
    finally:
        cur.close()
        conn.close()


def get_audit_entries_paginated(page=1, per_page=15, role_filter="", action_filter="", date_filter=""):
    conn = get_connection()
    cur = conn.cursor()
    try:
        where_clauses = []
        params = []

        if role_filter:
            where_clauses.append("LOWER(COALESCE(role, '')) = %s")
            params.append(role_filter.lower())

        if action_filter:
            where_clauses.append("LOWER(COALESCE(action, '')) = %s")
            params.append(action_filter.lower())

        parsed_date = None
        if date_filter:
            try:
                parsed_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = None
        if parsed_date:
            where_clauses.append("DATE(timestamp) = %s")
            params.append(parsed_date)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        cur.execute(f"SELECT COUNT(*) FROM audit_log {where_sql}", params)
        total = cur.fetchone()[0] or 0

        safe_page = max(1, int(page))
        safe_per_page = max(1, int(per_page))
        offset = (safe_page - 1) * safe_per_page

        query_params = params + [safe_per_page, offset]
        cur.execute(
            f"""
            SELECT action, role, defect_id, filename, new_status, timestamp, details
            FROM audit_log
            {where_sql}
            ORDER BY timestamp DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            query_params,
        )

        entries = []
        for action, role, defect_id, filename, new_status, timestamp, details in cur.fetchall():
            entries.append(
                {
                    "action": action,
                    "role": role,
                    "defect_id": defect_id,
                    "filename": filename,
                    "new_status": new_status,
                    "timestamp": str(timestamp),
                    "details": details,
                }
            )

        return entries, total
    finally:
        cur.close()
        conn.close()

def save_audit(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for item in data:
            cur.execute(
                """
                SELECT 1 FROM audit_log
                WHERE action = %s
                  AND COALESCE(role, '') = COALESCE(%s, '')
                  AND COALESCE(defect_id, -1) = COALESCE(%s, -1)
                  AND COALESCE(filename, '') = COALESCE(%s, '')
                  AND COALESCE(new_status, '') = COALESCE(%s, '')
                  AND timestamp = %s
                LIMIT 1
                """,
                (
                    item.get("action"),
                    item.get("role"),
                    item.get("defect_id"),
                    item.get("filename"),
                    item.get("new_status"),
                    item.get("timestamp", _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S")),
                ),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO audit_log (action, role, defect_id, filename, new_status, timestamp, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    item.get("action"),
                    item.get("role"),
                    item.get("defect_id"),
                    item.get("filename"),
                    item.get("new_status"),
                    item.get("timestamp", _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S")),
                    json.dumps(item.get("details", {})),
                ),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

# SIMPLE ENCRYPTION HELPERS
def encrypt_text(text):
    if not text:
        return ""
    return base64.b64encode(text.encode()).decode()

def decrypt_text(text):
    if not text:
        return ""
    return base64.b64decode(text.encode()).decode()

def load_evidence():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT ON (defect_id) defect_id, filename, uploaded_at, file_path, image_data
            FROM evidence
            ORDER BY defect_id, uploaded_at DESC
            """
        )
        return {
            str(defect_id): {
                "filename": filename,
                "uploaded_at": str(uploaded_at),
                "file_path": file_path,
                "image_data": image_data,
            }
            for defect_id, filename, uploaded_at, file_path, image_data in cur.fetchall()
        }
    finally:
        cur.close()
        conn.close()

def save_evidence(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for defect_id, item in data.items():
            cur.execute("DELETE FROM evidence WHERE defect_id = %s", (int(defect_id),))
            cur.execute(
                "INSERT INTO evidence (defect_id, filename, uploaded_at, file_path, image_data) VALUES (%s, %s, %s, %s, %s)",
                (
                    int(defect_id),
                    item.get("filename"),
                    item.get("uploaded_at", _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S")),
                    item.get("file_path", item.get("filename")),
                    item.get("image_data"),
                ),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_closed_evidence_appendix(role, claimant_user_id=None):
    """Return closed defects for role appendix view."""
    if role not in ["Homeowner", "Developer", "Legal", "Admin"]:
        return []

    if role == "Legal":
        defects = get_defects_for_role("Legal")
    elif role == "Homeowner":
        defects = get_defects_for_role("Homeowner")
    else:
        defects = get_defects_for_role("Developer")

    if claimant_user_id is not None:
        defects = [d for d in defects if d.get("user_id") == claimant_user_id]

    status_store = load_status()
    completion_store = load_completion_dates()
    evidence_store = load_evidence()

    appendix_rows = []
    for d in defects:
        defect_id = str(d.get("id"))
        status = status_store.get(defect_id, d.get("status"))
        completed_date = completion_store.get(defect_id, d.get("completed_date"))
        evidence = evidence_store.get(defect_id) or {}

        if not is_auto_closed(status, completed_date):
            continue

        appendix_rows.append(
            {
                "id": d.get("id"),
                "unit": d.get("unit", "-"),
                "status": "Closed",
                "reported_date": d.get("reported_date") or "-",
                "completed_date": completed_date or "-",
                "hda_compliant": calculate_hda_compliance(d.get("reported_date"), completed_date, status),
                "filename": evidence.get("filename", "-"),
                "file_path": evidence.get("file_path"),
                "uploaded_at": evidence.get("uploaded_at", "-"),
            }
        )

    appendix_rows.sort(key=lambda item: int(item["id"]) if str(item.get("id", "")).isdigit() else 0)
    return appendix_rows


def build_closed_appendix_lines(closed_evidence_appendix, language):
    """Build a consistent closed-case appendix text block for all roles."""
    if language == "ms":
        appendix_lines = [
            "",
            "LAMPIRAN A: BUTIRAN KES DITUTUP",
            "Kes ditutup dikecualikan daripada badan laporan utama dan disenaraikan di sini untuk rujukan sahaja.",
        ]
    else:
        appendix_lines = [
            "",
            "APPENDIX A: CLOSED CASE DETAILS",
            "Closed cases are excluded from the main report body and listed here for reference only.",
        ]

    if not closed_evidence_appendix:
        appendix_lines.append(
            "Tiada rekod kes ditutup buat masa ini."
            if language == "ms"
            else "No closed-case records are currently available."
        )
        return appendix_lines

    for idx, item in enumerate(closed_evidence_appendix, 1):
        header_prefix = f"{chr(64 + idx)}." if idx <= 26 else f"{idx}."
        closed_days = calculate_days_to_complete(item.get("reported_date"), item.get("completed_date"))

        if language == "ms":
            appendix_lines.append(f"{header_prefix} Kecacatan ID {item.get('id', '-')}:")
            appendix_lines.append(f"Unit: {item.get('unit', '-')}")
            appendix_lines.append(f"Tarikh Dilaporkan: {format_pdf_date(item.get('reported_date'))}")
            appendix_lines.append(f"Tarikh Siap: {format_pdf_date(item.get('completed_date'))}")
            appendix_lines.append(f"Tempoh Siap (Hari): {closed_days if closed_days is not None else '-'}")
            appendix_lines.append(f"Pematuhan HDA (30 Hari): {'Ya' if item.get('hda_compliant') else 'Tidak'}")
            appendix_lines.append(f"Peraturan Ditutup: Ditutup selepas {AUTO_CLOSE_DAYS} hari dari tarikh siap")
            appendix_lines.append(f"Muat Naik: {format_pdf_date(item.get('uploaded_at'))}")
            # Use a special marker ONLY when a real image filename is linked.
            # This prevents the PDF renderer from attempting to draw placeholder files.
            _fn_ms = (item.get('filename') or '').strip()
            if _fn_ms and _fn_ms not in ('-', 'gambar', 'image') and _is_valid_image_path(_fn_ms):
                appendix_lines.append("Gambar Kecacatan: [imej]")
            else:
                appendix_lines.append("Gambar Kecacatan: Tiada bukti imej dimuat naik.")
        else:
            appendix_lines.append(f"{header_prefix} Defect ID {item.get('id', '-')}:")
            appendix_lines.append(f"Unit: {item.get('unit', '-')}")
            appendix_lines.append(f"Reported Date: {format_pdf_date(item.get('reported_date'))}")
            appendix_lines.append(f"Completed: {format_pdf_date(item.get('completed_date'))}")
            appendix_lines.append(f"Days to Complete: {closed_days if closed_days is not None else '-'}")
            appendix_lines.append(f"HDA Compliance (30 Days): {'Yes' if item.get('hda_compliant') else 'No'}")
            appendix_lines.append(f"Closed Rule: Closed after {AUTO_CLOSE_DAYS} days from completion")
            appendix_lines.append(f"Uploaded: {format_pdf_date(item.get('uploaded_at'))}")
            # Use a special marker ONLY when a real image filename is linked.
            _fn_en = (item.get('filename') or '').strip()
            if _fn_en and _fn_en not in ('-', 'gambar', 'image') and _is_valid_image_path(_fn_en):
                appendix_lines.append("Defect Image: [image]")
            else:
                appendix_lines.append("Defect Image: No evidence image uploaded.")

        appendix_lines.append("")

    return appendix_lines


def _normalise_language(language):
    value = (language or "").strip().lower()
    if value in {"ms", "bm", "bahasa", "bahasa malaysia", "malay", "melayu"}:
        return "ms"
    return "en"


def strip_closed_appendix_section(report_text):
    text = (report_text or "").rstrip()
    marker = re.search(r"(?im)^(APPENDIX A:|LAMPIRAN A:)", text)
    if marker:
        return text[: marker.start()].rstrip()
    return text


def enforce_closed_appendix_format(report_text, closed_evidence_appendix, language):
    """Ensure closed appendix always uses the canonical line-by-line format."""
    text = strip_closed_appendix_section(report_text)

    appendix_lines = build_closed_appendix_lines(closed_evidence_appendix, language)
    return text + "\n" + "\n".join(appendix_lines)


def _format_generated_datetime(language):
    now = _now_app_timezone()
    if language == "ms":
        bulan_bm = {
            1: "Januari", 2: "Februari", 3: "Mac", 4: "April",
            5: "Mei", 6: "Jun", 7: "Julai", 8: "Ogos",
            9: "September", 10: "Oktober", 11: "November", 12: "Disember",
        }
        return f"{now.day:02d} {bulan_bm[now.month]} {now.year}, {now.strftime('%H:%M')}"
    return now.strftime("%d %B %Y, %H:%M")


def refresh_generated_datetime_line(report_text, language):
    if not report_text:
        return report_text

    label = "Tarikh Jana" if language == "ms" else "Generated Date"
    refreshed_line = f"{label}: {_format_generated_datetime(language)}"

    updated_text, count = re.subn(
        r"^(Tarikh Jana|Generated Date)\s*:\s*.*$",
        refreshed_line,
        report_text,
        count=1,
        flags=re.MULTILINE,
    )
    if count > 0:
        return updated_text

    lines = report_text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip():
            lines.insert(idx + 1, refreshed_line)
            break
    else:
        lines.append(refreshed_line)

    return "\n".join(lines)


def _format_claim_amount_for_report_text(raw_amount):
    value = str(raw_amount or "").strip()
    if not value or value in {"-", "Unknown"}:
        return "-"

    cleaned = value.replace("RM", "").replace(",", "").strip()
    try:
        amount_num = float(cleaned)
        return f"{amount_num:,.2f}"
    except Exception:
        return value


def enforce_case_background_section(report_text, language, claim_id, claim_amount, total_defects):
    claim_id_value = str(claim_id or "-")
    claim_amount_value = _format_claim_amount_for_report_text(claim_amount)
    defects_value = int(total_defects or 0)

    if language == "ms":
        section_text = (
            f"Nombor rujukan tuntutan untuk kes ini adalah {claim_id_value}, "
            f"dengan amaun tuntutan direkodkan sebanyak RM {claim_amount_value}. "
            f"Berdasarkan dokumen yang dikemukakan, jumlah keseluruhan kecacatan yang direkodkan adalah {defects_value}."
        )
        pattern = r"(1\.\s*Latar\s*Belakang\s*Kes\s*\n)(.*?)(?=\n\s*2\.|\Z)"
    else:
        section_text = (
            f"The claim reference number for this case is {claim_id_value}, "
            f"with a recorded claim amount of RM {claim_amount_value}. "
            f"Based on the submitted documentation, a total of {defects_value} defects have been recorded."
        )
        pattern = r"(1\.\s*Case\s*Background\s*\n)(.*?)(?=\n\s*2\.|\Z)"

    updated, count = re.subn(
        pattern,
        r"\1" + section_text + "\n",
        report_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return updated if count > 0 else report_text


def extract_claim_reference_from_report_text(report_text):
    text = report_text or ""
    match = re.search(r"\bTTPM/[A-Z]+/\d{4}/\d{6}\b", text)
    return match.group(0) if match else ""

def draw_justified_line(pdf, text, x, y, max_width, font_name, font_size):
    words = text.split()
    if len(words) <= 1:
        pdf.drawString(x, y, text)
        return

    pdf.setFont(font_name, font_size)

    words_width = sum(pdf.stringWidth(w, font_name, font_size) for w in words)
    space_needed = max_width - words_width
    if space_needed <= 0:
        pdf.drawString(x, y, text)
        return

    gap = space_needed / (len(words) - 1)

    cursor_x = x
    for w in words:
        pdf.drawString(cursor_x, y, w)
        cursor_x += pdf.stringWidth(w, font_name, font_size) + gap

def draw_footer(pdf, width, labels):
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(
        width - 50,
        25,
        f"{labels['page']} {pdf.getPageNumber()}"
    )

def draw_wrapped_text(pdf, text, x, y, max_width, font_name="Helvetica", font_size=9, leading=14):
    pdf.setFont(font_name, font_size)
    words = text.split()
    line = ""
    for word in words:
        test = line + " " + word if line else word
        if pdf.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            pdf.drawString(x, y, line)
            y -= leading
            line = word
    if line:
        pdf.drawString(x, y, line)
        y -= leading
    return y

def format_pdf_date(date_val):
    if not date_val or date_val == "-":
        return "-"
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%Y-%m-%d %H:%M')
    elif isinstance(date_val, str):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return date_val
    return str(date_val)

def draw_table_row(pdf, label_text, colon_x, val_x, val_text, y, max_val_width, font_name="Helvetica", font_size=9, leading=14):
    pdf.setFont(font_name, font_size)
    orig_y = y
    
    y_label = y
    for line in str(label_text).split('\n'):
        pdf.drawString(60, y_label, line)
        y_label -= leading
        
    pdf.drawString(colon_x, orig_y, ":")
    y_val = draw_wrapped_text(pdf, str(val_text), val_x, orig_y, max_val_width, font_name, font_size, leading)
    
    # Return the lowest y to start the next row
    return min(y_label, y_val)

# =================================================
# DASHBOARD ROUTE (THIS MAKES THE UI OPEN)
# =================================================
@routes.route("/")
@login_required
def dashboard():
    # Role discovery - normalized to capitalized for template switching
    _raw_role = _current_role()
    role = (_raw_role.capitalize() if _raw_role else "Legal")
    if role == "Lawyer": role = "Legal"
    
    # Check if homeowner has completed mandatory profile details
    # Exempt profile and settings pages to prevent redirect loops
    from flask import request
    if role == "Homeowner":
        exempt_endpoints = ['module3.profile', 'module3.settings', 'module3.update_profile', 'module3.change_password']
        if not request.endpoint or request.endpoint not in exempt_endpoints:
            user = User.query.get(current_user.id)
            if not user.housing_project or not user.unit or not user.correspondence_address:
                flash('Please complete your property details to continue', 'warning')
                return redirect(url_for('module3.profile'))
    
    auto_close_completed_cases(trigger_role=role)
    backfill_missing_deadlines()
    
    if role == "Admin":
        defects = get_defects_for_role("Developer")
        stats = calculate_stats(defects)
        users = User.query.all()
        total_users = User.query.count()
        audit_role = (request.args.get("audit_role") or "").strip()
        audit_action = (request.args.get("audit_action") or "").strip()
        audit_date = (request.args.get("audit_date") or "").strip()

        try:
            audit_page = int(request.args.get("audit_page", "1"))
        except ValueError:
            audit_page = 1

        per_page = 15
        audit_entries, total_audit = get_audit_entries_paginated(
            page=audit_page,
            per_page=per_page,
            role_filter=audit_role,
            action_filter=audit_action,
            date_filter=audit_date,
        )

        total_pages = (total_audit + per_page - 1) // per_page if total_audit else 1
        if audit_page > total_pages:
            audit_page = total_pages
            audit_entries, total_audit = get_audit_entries_paginated(
                page=audit_page,
                per_page=per_page,
                role_filter=audit_role,
                action_filter=audit_action,
                date_filter=audit_date,
            )

        audit_start = 0 if total_audit == 0 else (audit_page - 1) * per_page + 1
        audit_end = min(audit_page * per_page, total_audit)
        audit_roles, audit_actions = get_audit_filter_options()

        return render_template(
            "module3/dashboard_admin.html",
            role=role,
            stats=stats,
            defects=defects,
            users=users,
            total_users=total_users,
            audit_entries=audit_entries,
            total_audit=total_audit,
            audit_page=audit_page,
            total_pages=total_pages,
            per_page=per_page,
            audit_start=audit_start,
            audit_end=audit_end,
            audit_role=audit_role,
            audit_action=audit_action,
            audit_date=audit_date,
            audit_roles=audit_roles,
            audit_actions=audit_actions,
            support_contact=SUPPORT_CONTACT,
            username=_current_actor_name() or "admin",
        )

    defects = get_defects_for_role(role)
    remarks_store = load_remarks()
    status_store = load_status()
    completion_store = load_completion_dates()
    evidence_store = load_evidence()

    for d in defects:
        # Status is shared across all roles
        d["status"] = status_store.get(str(d["id"]), d["status"])

        # 🔥 RESTORE COMPLETION DATE
        d["completed_date"] = completion_store.get(
        str(d["id"]),
        d.get("completed_date")
        )

        # Restore evidence info
        evidence_data = evidence_store.get(str(d["id"]))
        if evidence_data:
            d["evidence_uploaded"] = True
            d["evidence_filename"] = evidence_data.get("filename")
            d["evidence_uploaded_at"] = evidence_data.get("uploaded_at")
        else:
            d["evidence_uploaded"] = False
            d["evidence_filename"] = None
            d["evidence_uploaded_at"] = None

        # Remarks are ONLY visible to Homeowner
        if role == "Homeowner":
            d["remarks"] = remarks_store.get(str(d["id"]), "")
        else:
            d["remarks"] = ""  # Hide remarks for Developer & Legal

    stats = calculate_stats(defects)
    claim_input = None
    if role in ["Homeowner", "Developer", "Legal"]:
        user_info = get_current_user()
        if role == "Homeowner":
            claim_input = get_homeowner_claim_details(_current_user_id())
        if role in ["Developer", "Legal"]:
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT company_name, registration_number, email, phone_number, address
                    FROM report_respondent_profile
                    WHERE respondent_id = %s
                    """,
                    (_current_user_id(),),
                )
                row = cur.fetchone()
                if row:
                    user_info = {
                        "name": row[0] or user_info["name"],
                        "company_name": row[0] or user_info["name"],
                        "registration_number": row[1] or "",
                        "email": row[2] or user_info.get("email", ""),
                        "phone_number": row[3] or "",
                        "unit": row[4] or "",
                    }
                else:
                    user_info["company_name"] = user_info["name"]
            finally:
                cur.close()
                conn.close()
    else:
        user_info = {"name": _current_actor_name() or role, "unit": ""}

    homeowner_claimants = (
        get_homeowner_claimants(lawyer_user_id=_current_user_id())
        if role == "Legal"
        else get_homeowner_claimants()
        if role == "Developer"
        else []
    )

    template = (
        "module3/dashboard_homeowner.html"
        if role == "Homeowner"
        else "module3/dashboard_developer.html"
        if role == "Developer"
        else "module3/dashboard_legal.html"
    )

    return render_template(
        template,
        role=role,
        defects=defects,
        stats=stats,
        user_info=user_info,
        claim_input=claim_input,
        state_court_map=STATE_COURT_MAP,
        state_options=list(STATE_COURT_MAP.keys()),
        item_service_options=list(ITEM_SERVICE_TRANSLATIONS.keys()),
        homeowner_claimants=homeowner_claimants,
        registered_developers=_get_registered_developers() if role == "Homeowner" else [],
        available_lawyers=_get_registered_lawyers() if role == "Homeowner" else [],
        support_contact=SUPPORT_CONTACT,
        username=_current_actor_name(),
    )


@routes.route("/admin_delete_user", methods=["POST"])
@login_required
def admin_delete_user():
    if current_user.user_type != "admin":
        abort(403)

    user_id = request.form.get("user_id", type=int)
    if not user_id:
        flash("Invalid user ID.", "danger")
        return redirect(url_for("module3.dashboard"))

    if user_id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("module3.dashboard"))

    target = User.query.get(user_id)
    if not target:
        flash("User not found.", "danger")
        return redirect(url_for("module3.dashboard"))

    db.session.delete(target)
    db.session.commit()

    _append_audit_event(
        action=f"Deleted user {target.email} (id={target.id})",
        role="Admin",
    )
    flash(f"User {target.email} has been deleted.", "success")
    return redirect(url_for("module3.dashboard"))


@routes.route("/admin_update_user_role", methods=["POST"])
@login_required
def admin_update_user_role():
    if current_user.user_type != "admin":
        abort(403)

    user_id = request.form.get("user_id", type=int)
    new_user_type = request.form.get("user_type", "").strip().lower()

    if not user_id or new_user_type not in ("homeowner", "developer", "lawyer", "admin"):
        flash("Invalid request parameters.", "danger")
        return redirect(url_for("module3.dashboard"))

    if user_id == current_user.id:
        flash("You cannot change your own role.", "danger")
        return redirect(url_for("module3.dashboard"))

    target = User.query.get(user_id)
    if not target:
        flash("User not found.", "danger")
        return redirect(url_for("module3.dashboard"))

    # Sync both user_type and legacy role field
    target.user_type = new_user_type
    target.role = new_user_type.capitalize()
    db.session.commit()

    _append_audit_event(
        action=f"Changed user {target.email} (id={target.id}) role to {new_user_type}",
        role="Admin",
    )
    flash(f"User {target.email} role updated to {new_user_type.capitalize()}.", "success")
    return redirect(url_for("module3.dashboard"))


@routes.route("/save_homeowner_claim_details", methods=["POST"])
@login_required
def save_homeowner_claim_details():
    if _current_role_key() != "homeowner":
        return jsonify({"success": False, "error": "Only homeowner can update claim details."}), 403

    data = request.get_json(silent=True) or {}
    court_location = (data.get("court_location") or "").strip()
    state_name = (data.get("state_name") or "").strip()
    item_service = (data.get("item_service") or "").strip()
    transaction_date = (data.get("transaction_date") or "").strip()
    claim_amount = (data.get("claim_amount") or "").strip()
    homeowner_address = (data.get("homeowner_address") or "").strip()
    respondent_company_name = (data.get("respondent_company_name") or "").strip()
    respondent_registration_number = (data.get("respondent_registration_number") or "").strip()
    respondent_email = (data.get("respondent_email") or "").strip()
    respondent_phone_number = (data.get("respondent_phone_number") or "").strip()
    respondent_address = (data.get("respondent_address") or "").strip()
    other_developer_name = (data.get("other_developer_name") or "").strip()
    assigned_lawyer_id_raw = str(data.get("assigned_lawyer_id") or "").strip()

    if respondent_company_name == "others" and other_developer_name:
        respondent_company_name = other_developer_name

    selected_dev_id = None
    if respondent_company_name.isdigit():
        selected_dev_id = int(respondent_company_name)

    assigned_lawyer_id = None
    if assigned_lawyer_id_raw:
        if not assigned_lawyer_id_raw.isdigit():
            return jsonify({"success": False, "error": "Invalid legal representative selection."}), 400
        assigned_lawyer_id = int(assigned_lawyer_id_raw)

    if not court_location:
        return jsonify({"success": False, "error": "Court location is required."}), 400
    if not state_name:
        return jsonify({"success": False, "error": "State is required."}), 400
    if not transaction_date:
        return jsonify({"success": False, "error": "Transaction date is required."}), 400
    if not claim_amount:
        return jsonify({"success": False, "error": "Claim amount is required."}), 400
    if not homeowner_address:
        return jsonify({"success": False, "error": "Homeowner address is required."}), 400

    if not item_service:
        item_service = _default_item_service()
    item_service = _normalise_item_service(item_service)

    allowed_courts = _get_court_locations_for_state(state_name)
    if not allowed_courts:
        return jsonify({"success": False, "error": "Please choose a valid state from the dropdown."}), 400
    if court_location not in allowed_courts:
        return jsonify({"success": False, "error": f"Court location must match the selected state: {', '.join(allowed_courts)}."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_developer_id INTEGER")
        cur.execute("ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_lawyer_id INTEGER")
        cur.execute("ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS court_location VARCHAR(255)")
        cur.execute("ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS state_name VARCHAR(100)")
        cur.execute("ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS claim_amount VARCHAR(100)")
        cur.execute("ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS item_service VARCHAR(255)")
        cur.execute("ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS transaction_date DATE")
        cur.execute("ALTER TABLE report_respondent_profile ADD COLUMN IF NOT EXISTS homeowner_id INTEGER")

        user_id = _current_user_id()

        if assigned_lawyer_id is not None:
            cur.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s
                  AND (user_type = 'lawyer' OR role = 'Legal')
                LIMIT 1
                """,
                (assigned_lawyer_id,),
            )
            if not cur.fetchone():
                return jsonify({"success": False, "error": "Selected legal representative not found."}), 400

        # Graceful handling for registered developers
        if selected_dev_id:
            cur.execute(
                "SELECT company_name, email, phone_number, company_address, ssm_registration FROM users WHERE id = %s",
                (selected_dev_id,),
            )
            dev_row = cur.fetchone()
            if dev_row:
                respondent_company_name = dev_row[0] or respondent_company_name
                respondent_email = dev_row[1] or respondent_email
                respondent_phone_number = dev_row[2] or respondent_phone_number
                respondent_address = dev_row[3] or respondent_address
                respondent_registration_number = dev_row[4] or respondent_registration_number

        cur.execute(
            "SELECT full_name, email, unit, ic_number, phone_number FROM users WHERE id = %s",
            (user_id,),
        )
        user_row = cur.fetchone()
        if not user_row:
            return jsonify({"success": False, "error": "User not found."}), 404

        cur.execute(
            "SELECT name FROM report_homeowner_profile WHERE homeowner_id = %s",
            (user_id,),
        )
        existing_profile = cur.fetchone()
        profile_name = None
        if existing_profile and existing_profile[0]:
            profile_name = existing_profile[0].strip()
        if not profile_name:
            profile_name = (user_row[0] or "").strip()

        cur.execute(
            """
            INSERT INTO report_homeowner_profile (
                homeowner_id, name, ic_number, email, phone_number, address, court_location, state_name, item_service, transaction_date, claim_amount, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (homeowner_id) DO UPDATE
            SET name = EXCLUDED.name,
                ic_number = EXCLUDED.ic_number,
                email = EXCLUDED.email,
                phone_number = EXCLUDED.phone_number,
                address = EXCLUDED.address,
                court_location = EXCLUDED.court_location,
                state_name = EXCLUDED.state_name,
                item_service = EXCLUDED.item_service,
                transaction_date = EXCLUDED.transaction_date,
                claim_amount = EXCLUDED.claim_amount,
                updated_at = NOW()
            """,
            (
                user_id,
                profile_name,
                user_row[3],
                user_row[1],
                user_row[4],
                homeowner_address,
                court_location,
                state_name,
                item_service,
                transaction_date,
                claim_amount,
            ),
        )

        cur.execute(
            """
            INSERT INTO report_respondent_profile (
                respondent_id, homeowner_id, company_name, registration_number, email, phone_number, address, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (respondent_id) DO UPDATE
            SET homeowner_id = EXCLUDED.homeowner_id,
                company_name = EXCLUDED.company_name,
                registration_number = EXCLUDED.registration_number,
                email = EXCLUDED.email,
                phone_number = EXCLUDED.phone_number,
                address = EXCLUDED.address,
                updated_at = NOW()
            """,
            (
                # If we have a selected_dev_id, we use it as the PK, otherwise we use user_id (homeowner) as a placeholder.
                # However, to avoid conflicts (multiple homeowners having different respondents but same ID),
                # we should probably stick with user_id as the PK for the respondent profile if it's meant to be 1:1.
                # Given the current schema, we'll keep it as user_id to ensure each homeowner has their own respondent data.
                user_id, 
                user_id,
                respondent_company_name or "-",
                respondent_registration_number or "-",
                respondent_email or "-",
                respondent_phone_number or "-",
                respondent_address or "-",
            ),
        )

        # LINK DEFECTS TO DEVELOPER
        if selected_dev_id:
            cur.execute(
                "UPDATE defects SET assigned_developer_id = %s WHERE user_id = %s",
                (selected_dev_id, user_id)
            )
        else:
            cur.execute(
                "UPDATE defects SET assigned_developer_id = NULL WHERE user_id = %s",
                (user_id,)
            )

        cur.execute(
            "UPDATE defects SET assigned_lawyer_id = %s WHERE user_id = %s",
            (assigned_lawyer_id, user_id)
        )

        # ── Persist developer/lawyer assignment on the User record ────────────
        cur.execute(
            "UPDATE users SET assigned_developer_id = %s, assigned_lawyer_id = %s WHERE id = %s",
            (selected_dev_id, assigned_lawyer_id, user_id)
        )

        conn.commit()
        return jsonify({"success": True, "message": "Claim details saved."})
    finally:
        cur.close()
        conn.close()


# =================================================
# UPLOAD EVIDENCE IMAGE
# =================================================
@routes.route("/upload_evidence", methods=["POST"])
@login_required
def upload_evidence():
    """
    Upload evidence image for a specific defect.
    Images are stored in the evidence folder with naming: defect_{id}.jpg
    Only the uploader can see their uploaded images (privacy).
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        defect_id = request.form.get('defect_id')
        
        if not defect_id:
            return jsonify({"error": "No defect ID provided"}), 400
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "error": "File type not allowed. Allowed types: jpg, jpeg, png, tif, tiff"
            }), 400

        from app.models import Defect
        from app.utils.auth_helper import authorize_defect_access
        defect = Defect.query.get(defect_id)
        if not defect:
            return jsonify({"error": "Defect not found"}), 404
        authorize_defect_access(defect)

        import uuid
        from PIL import Image

        # Magic Bytes Validation
        try:
            head = file.read(512)
            file.seek(0)
            img = Image.open(file)
            img.verify()
            file.seek(0)
        except Exception:
            return jsonify({"error": "Invalid image content."}), 400

        # Create evidence directory if not exists
        evidence_dir = os.path.realpath(os.path.join(current_app.root_path, "evidence"))
        os.makedirs(evidence_dir, exist_ok=True)
        
        # Get original extension
        ext = file.filename.rsplit('.', 1)[1].lower()

        filename = f"{uuid.uuid4().hex}.{ext}"

        # Read file and encode to Base64 for database storage
        file_content = file.read()
        image_data = base64.b64encode(file_content).decode('utf-8')

        # Save evidence metadata with timestamp
        now_local = _now_app_timezone()

        uploaded_at = now_local.strftime("%Y-%m-%d %H:%M:%S")

        evidence_img = load_evidence()
        evidence_img[defect_id] = {
            "filename": filename,
            "uploaded_at": uploaded_at,
            "file_path": filename,
            "image_data": image_data,
        }
        save_evidence(evidence_img)

        # AUDIT LOG - EVIDENCE UPLOADED
        _append_audit_event(
            action="Evidence Uploaded",
            role=_current_role(),
            defect_id=defect_id,
            filename=filename,
            details={
                "username": _current_actor_name(),
                "defect_id": defect_id,
                "filename": filename,
                "file_extension": ext,
                "uploaded_at": evidence_img[defect_id].get("uploaded_at"),
            },
        )
        
        return jsonify({
            "success": True,
            "message": f"Evidence uploaded for defect #{defect_id}",
            "filename": filename,
            "defect_id": defect_id,
            "uploaded_at": uploaded_at,
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =================================================
# CHECK IF EVIDENCE EXISTS
# =================================================
@routes.route("/evidence_exists/<defect_id>")
@login_required
def evidence_exists(defect_id):
    """
    Check if evidence image exists for a defect.
    """
    from app.models import Defect, Evidence
    from app.utils.auth_helper import authorize_defect_access
    defect = Defect.query.get(defect_id)
    if not defect:
        return jsonify({"exists": False, "defect_id": defect_id})
    authorize_defect_access(defect)

    # 1. Check database for image_data
    evidence = Evidence.query.filter_by(defect_id=defect_id).first()
    if evidence and evidence.image_data:
        return jsonify({"exists": True, "defect_id": defect_id})

    # 2. Fallback: check file on disk
    evidence_dir = os.path.join(current_app.root_path, "evidence")
    for ext in ALLOWED_EXTENSIONS:
        filename = f"defect_{defect_id}.{ext}"
        filepath = os.path.join(evidence_dir, filename)
        if os.path.exists(filepath):
            return jsonify({
                "exists": True,
                "defect_id": defect_id
            })

    return jsonify({
        "exists": False,
        "defect_id": defect_id
    })


# =================================================
# SERVE EVIDENCE IMAGE FILE
# =================================================
@routes.route("/evidence_image/<path:filename>")
@login_required
def serve_evidence_image(filename):
    """
    Serve an evidence image file stored in app/evidence/ (outside static/).
    Only authenticated users can access these files.
    """
    from flask import send_from_directory, abort, Response
    
    # Find defect associated with this evidence file
    from app.models import Evidence
    evidence = Evidence.query.filter_by(filename=filename).first()
    if not evidence:
        abort(404)
    
    # Check if user has access to the defect
    from app.models import Defect
    defect = Defect.query.get(evidence.defect_id)
    if not defect:
        abort(404)
    
    # Reuse existing authorization helper (it aborts internally on failure)
    from app.utils.auth_helper import authorize_defect_access
    authorize_defect_access(defect)

    # 1. Serve from database (Base64) — preferred for new uploads
    if evidence.image_data:
        return Response(
            base64.b64decode(evidence.image_data),
            mimetype='image/png'
        )
    
    # 2. Fallback to file on disk
    evidence_dir = os.path.join(current_app.root_path, "evidence")
    return send_from_directory(evidence_dir, filename)


# =================================================
# ADD / SAVE REMARK (NOTE)
# =================================================
@routes.route("/add_remark", methods=["POST"])
@login_required
def add_remark():
    data = request.get_json()
    role = _current_role()

    # Only Homeowner is allowed to add remarks
    if _current_role_key() != "homeowner":
        return jsonify({"error": "Unauthorized"}), 403

    defect_id = str(data.get("id"))

    from app.models import Defect
    from app.utils.auth_helper import authorize_defect_access
    defect = Defect.query.get(defect_id)
    if not defect:
        return jsonify({"error": "Defect not found"}), 404
    authorize_defect_access(defect)
    remark = data.get("remark")

    if remark and len(remark) > 0:
        remark = remark[0].upper() + remark[1:]

    if not defect_id or not remark:
        return jsonify({"error": "Invalid data"}), 400

    remarks = load_remarks()
    remarks[defect_id] = remark
    save_remarks(remarks)

    # AUDIT LOG - REMARK ADDED
    _append_audit_event(
        action="Remark Added",
        defect_id=defect_id,
        role=role,
        details={
            "username": _current_actor_name(),
            "remark": remark,
            "remark_length": len(remark),
        },
    )

    return jsonify({"success": True})

# =================================================
# UPDATE STATUS (DEVELOPER)
# =================================================
@routes.route("/update_status", methods=["POST"])
@login_required
def update_status():
    if _current_role_key() not in ["developer", "admin"]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    role = _current_role()

    defect_id = str(data.get("id"))

    from app.models import Defect
    from app.utils.auth_helper import authorize_defect_access
    defect = Defect.query.get(defect_id)
    if not defect:
        return jsonify({"success": False, "message": "Defect not found"}), 404
    authorize_defect_access(defect)
    requested_status = data.get("status")
    # Closed is system-derived only (auto-close), never manually set.
    new_status = requested_status
    completed_date = data.get("completed_date")
    deadline = (data.get("deadline") or "").strip()

    ALLOWED_STATUS = {
        "Pending",
        "In Progress",
        "Completed",
        "Delayed"
    }

    if not defect_id or new_status not in ALLOWED_STATUS:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    if requested_status == "Closed":
        return jsonify({"success": False, "message": "Closed status is automatic and cannot be set manually"}), 400

    if new_status == "Completed" and not completed_date:
        return jsonify({"success": False, "message": "Please enter completion date when status is Completed"}), 400

    if new_status == "Completed":
        try:
            completed_date_obj = datetime.strptime(str(completed_date), "%Y-%m-%d").date()
        except Exception:
            return jsonify({"success": False, "message": "Invalid completion date format"}), 400

        if completed_date_obj > _now_app_timezone().date():
            return jsonify({"success": False, "message": "Completion date cannot be in the future"}), 400

    parsed_deadline = None
    if deadline:
        try:
            parsed_deadline = datetime.strptime(deadline, "%Y-%m-%d").date()
        except Exception:
            return jsonify({"success": False, "message": "Invalid deadline date format"}), 400

    effective_completed_date = completed_date

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT status, deadline, user_id FROM defects WHERE id = %s",
            (int(defect_id),),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Defect not found"}), 404

        old_status = row[0]
        old_deadline = _to_iso(row[1])
        defect_owner_id = row[2]

        cur.execute(
            "UPDATE defects SET status = %s WHERE id = %s",
            (new_status, int(defect_id)),
        )

        if parsed_deadline is not None:
            cur.execute(
                "UPDATE defects SET deadline = %s WHERE id = %s",
                (parsed_deadline, int(defect_id)),
            )

        # Keep defects.completed_date and completion_dates synchronized for the same defect only.
        if new_status == "Completed" and effective_completed_date:
            cur.execute(
                "UPDATE defects SET completed_date = %s WHERE id = %s",
                (effective_completed_date, int(defect_id)),
            )
            # Upsert: delete any existing row then insert fresh.
            # (Avoids ON CONFLICT which requires a unique index that may not exist on older DBs.)
            cur.execute("DELETE FROM completion_dates WHERE defect_id = %s", (int(defect_id),))
            cur.execute(
                "INSERT INTO completion_dates (defect_id, completion_date) VALUES (%s, %s)",
                (int(defect_id), effective_completed_date),
            )
        else:
            cur.execute("DELETE FROM completion_dates WHERE defect_id = %s", (int(defect_id),))
            cur.execute(
                "UPDATE defects SET completed_date = NULL WHERE id = %s",
                (int(defect_id),),
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        msg = str(e)
        if "check constraint" in msg.lower() and "status" in msg.lower():
            return jsonify({"success": False, "message": "Database status rule rejected this value. Please ensure 'Delayed' is allowed in defects.status constraint."}), 400
        return jsonify({"success": False, "message": f"Failed to save status: {msg}"}), 400
    finally:
        cur.close()
        conn.close()

    # AUDIT LOG: STATUS UPDATE
    _append_audit_event(
        action="Status Updated",
        role=role,
        defect_id=defect_id,
        new_status=new_status,
        details={
            "username": _current_actor_name(),
            "old_status": old_status,
            "requested_status": requested_status,
            "new_status": new_status,
            "requested_completed_date": completed_date,
            "stored_completed_date": effective_completed_date if new_status == "Completed" else None,
            "old_deadline": old_deadline,
            "new_deadline": deadline or old_deadline,
        },
    )

    # ── NOTIFICATION: status change ──
    if old_status != new_status and defect_owner_id:
        try:
            from ..models import Notification
            from ..extensions import db

            actor_name = _current_actor_name()
            if defect_owner_id != current_user.id:
                db.session.add(Notification(
                    user_id=defect_owner_id,
                    title="Status Updated",
                    message=f"Defect #{defect_id} changed from '{old_status}' to '{new_status}' by {actor_name}",
                    notification_type="status_update",
                ))
                db.session.commit()
        except Exception:
            current_app.logger.warning("Failed to create status-change notification", exc_info=True)

    return jsonify({"success": True})

# =================================================
# GENERATE AI REPORT (JSON)
# =================================================
@routes.route("/generate_ai_report", methods=["POST"])
@login_required
def generate_ai_report_api():
    try:
        backfill_missing_deadlines()
        data = request.get_json(silent=True) or {}
        user_type = (_current_role() or "").lower()
        if user_type not in ["homeowner", "developer", "lawyer", "legal"]:
            return jsonify({"error": "Unauthorized role"}), 403

        # Normalise role for internal module logic
        role = user_type.capitalize()
        if role == "Lawyer": role = "Legal"
        auto_close_completed_cases(trigger_role=role)
        language = _normalise_language(data.get("language", "ms"))
        project_filter = _normalise_project_filter_value(data.get("project_filter"))
        defects = get_defects_for_role(role)
        defects = filter_defects_by_project(defects, project_filter)
        
        # Validate: Check if there are any defects at all
        if not defects or len(defects) == 0:
            return jsonify({
                "error": "No defects available to generate report",
                "details": (
                    f"No defects found for project '{project_filter}'."
                    if project_filter
                    else "Please add defects before generating a report."
                )
            }), 400
            
        claimant_user_id = data.get("claimant_user_id")
        claimant_user_id = int(claimant_user_id) if str(claimant_user_id or "").strip().isdigit() else None

        claimant_user_id = _resolve_claimant_user_id(role, claimant_user_id, defects)
        if role == "Legal" and claimant_user_id is None:
            return jsonify({
                "error": "No authorized homeowner selected for this lawyer.",
                "details": "This legal account can only access cases explicitly assigned to it.",
            }), 403

        if role == "Legal" and claimant_user_id is not None:
            defects = [d for d in defects if d.get("user_id") == claimant_user_id]
            defects = filter_defects_by_project(defects, project_filter)
            if not defects:
                return jsonify({
                    "error": "No assigned defects found for the selected homeowner.",
                    "details": "This legal account can only generate reports for homeowners assigned to it.",
                }), 403

        requirement_errors = validate_report_requirements(role=role, user_id=_current_user_id(), claimant_user_id=claimant_user_id)
        if requirement_errors:
            return jsonify(
                {
                    "error": "Cannot generate report. Required profile/case data is incomplete.",
                    "details": requirement_errors,
                }
            ), 400

        closed_evidence_appendix = get_closed_evidence_appendix(role, claimant_user_id=claimant_user_id)
        
        remarks_store = load_remarks()
        status_store = load_status()
        completion_store = load_completion_dates()
        evidence_store = load_evidence()

        # LOAD LATEST STATUS + CALCULATE
        for d in defects:
            d["status"] = status_store.get(str(d["id"]), d["status"])
            d["completed_date"] = completion_store.get(
                str(d["id"]),
                d.get("completed_date")
            )
            d["closed"] = is_auto_closed(d["status"], d.get("completed_date"))
            d["display_status"] = "Closed" if d["closed"] else d["status"]
            evidence_data = evidence_store.get(str(d["id"]))
            if evidence_data:
                d["evidence_uploaded"] = True
                d["evidence_filename"] = evidence_data.get("filename")
            else:
                d["evidence_uploaded"] = False
                d["evidence_filename"] = None
            d["remarks"] = remarks_store.get(str(d["id"]), "")  # optional
            d["hda_compliant"] = calculate_hda_compliance(
                d.get("reported_date"),
                d.get("completed_date"),
                d.get("status")
            )

            d["is_overdue"] = calculate_overdue(
                d.get("deadline"),
                d.get("completed_date"),
                d.get("status")
            )
            # NORMALISE urgency → priority (BEFORE translate)
            if "urgency" in d and not d.get("priority"):
                d["priority"] = d["urgency"]

        defects = [d for d in defects if not d.get("closed")]
        
        if not defects and not closed_evidence_appendix:
            return jsonify({
                "error": "No defects available to generate report",
                "details": "All defects are closed or none exist."
            }), 400
        
        # Validate: Check for required fields in defects
        missing_fields = []
        for d in defects:
            if not d.get("id"):
                missing_fields.append(f"Defect missing ID")
            if not d.get("desc"):
                missing_fields.append(f"Defect #{d.get('id', 'unknown')} missing Description")
            # unit is only required for module3-form defects;
            # pinpoint defects from module2 use element/location as identifiers.
            if not d.get("unit") and not d.get("element") and not d.get("location"):
                missing_fields.append(
                    f"Defect #{d.get('id', 'unknown')} has no Unit, Element, or Location — "
                    "please add a Room/Area via the 3D visualizer."
                )
            # Back-fill unit for AI context when only element/location available
            if not d.get("unit"):
                d["unit"] = d.get("location") or d.get("element") or "Pinpointed (No Unit)"

        if missing_fields:
            return jsonify({
                "error": "Missing required data in defects",
                "details": f"Please complete defect information: {', '.join(missing_fields[:3])}"
            }), 400

        # LOCK STATUS (BACKEND AUTHORITY)
        for d in defects:
            d["_status_raw"] = d["status"]
        
        # AI TRANSLATION (CACHE FOLLOW ROLE)
        defects = translate_defects_cached(
            defects,
            language=language,
            role=role
        )

        # ==========================================
        # FORCE REMARKS LANGUAGE CONSISTENTLY
        # (ONLY FOR AI REPORT, NOT PDF)
        # ==========================================
        if language == "ms":
            for d in defects:
                if d.get("remarks"):
                    d["remarks"] = translate_remark_cached(
                        d["remarks"],
                        language="ms",
                        role=role
                    )
        elif language == "en":
            for d in defects:
                if d.get("remarks"):
                    d["remarks"] = translate_remark_cached(
                        d["remarks"],
                        language="en",
                        role=role
                    )

        if role.lower() != "homeowner":
            for d in defects:
                d["remarks"] = ""
        
        # STEP 1: NORMALISE STATUS BEFORE STATS
        for d in defects:
            if d["status"] in STATUS_NORMALISE:
                d["status"] = STATUS_NORMALISE[d["status"]]
                
        # ==========================
        # VALIDATE DEFECT DATA
        # ==========================
        validation_errors = []

        for d in defects:
            if not d.get("reported_date"):
                validation_errors.append(f"Defect {d['id']} missing reported date")

            if not d.get("deadline"):
                validation_errors.append(f"Defect {d['id']} missing deadline")

            if d.get("status") == "Completed" and not d.get("completed_date"):
                validation_errors.append(f"Defect {d['id']} marked Completed but missing completion date")

        if validation_errors:
            return jsonify({
                "error": "Incomplete defect data",
                "details": validation_errors
            }), 400

        # Reuse previously generated report when the source defect snapshot is unchanged.
        snapshot_payload = {
            "report_format_version": 6,
            "role": role,
            "language": language,
            "project_filter": project_filter,
            "appendix_schema_version": 2 if role in ["Homeowner", "Developer", "Legal", "Admin"] else 1,
            "defects": [
                {
                    "id": d.get("id"),
                    "unit": d.get("unit"),
                    "desc": d.get("desc"),
                    "status": d.get("status"),
                    "reported_date": d.get("reported_date"),
                    "deadline": d.get("deadline"),
                    "completed_date": d.get("completed_date"),
                    "remarks": d.get("remarks"),
                    "urgency": d.get("urgency"),
                }
                for d in defects
            ],
            "closed_evidence_appendix": [
                {
                    "id": item.get("id"),
                    "filename": item.get("filename"),
                    "uploaded_at": item.get("uploaded_at"),
                    "completed_date": item.get("completed_date"),
                }
                for item in closed_evidence_appendix
            ] if role in ["Homeowner", "Developer", "Legal", "Admin"] else [],
        }
        data_hash = hashlib.sha256(
            json.dumps(snapshot_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT details
                FROM audit_log
                WHERE action = 'AI Report Generated'
                  AND role = %s
                  AND details->>'language' = %s
                  AND details->>'data_hash' = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (role, language, data_hash),
            )
            existing = cur.fetchone()

            if existing and existing[0]:
                details = existing[0]
                cached_version = int(details.get("version", 0))
                if cached_version > 0:
                    cached_version_str = str(cached_version)
                    cur.execute(
                        """
                        SELECT report_text
                        FROM report_versions
                        WHERE role = %s AND version_no = %s AND language = %s
                        LIMIT 1
                        """,
                        (role, cached_version_str, language),
                    )
                    cached_row = cur.fetchone()
                    if cached_row and cached_row[0]:
                        # Even for cached narrative, rebuild case metadata so claim reference
                        # follows the current backend serial strategy.
                        cached_stats = calculate_stats(defects)
                        cached_case_key = build_case_key(
                            role=role,
                            user_id=claimant_user_id or _current_user_id(),
                            defects=defects,
                        )
                        cached_report_data = build_report_data(
                            role,
                            defects,
                            cached_stats,
                            user_id=_current_user_id(),
                            case_key=cached_case_key,
                            claimant_user_id=claimant_user_id,
                            project_filter=project_filter,
                            closed_count=len(closed_evidence_appendix),
                        )

                        report_text = enforce_closed_appendix_format(
                            cached_row[0],
                            closed_evidence_appendix,
                            language,
                        )
                        cached_case_info = cached_report_data.get("case_info", {})
                        report_text = enforce_case_background_section(
                            report_text,
                            language,
                            cached_case_info.get("claim_id"),
                            cached_case_info.get("claim_amount"),
                            cached_stats.get("total", len(defects)),
                        )
                        report_text = refresh_generated_datetime_line(report_text, language)
                        return jsonify({
                            "generated_at": _now_app_timezone().strftime("%d/%m/%Y %H:%M:%S"),
                            "role": role,
                            "language": language,
                            "report": report_text
                        })
        finally:
            cur.close()
            conn.close()

        # BUILD REPORT
        stats = calculate_stats(defects)
        case_key = build_case_key(role=role, user_id=claimant_user_id or _current_user_id(), defects=defects)
        report_data = build_report_data(
            role,
            defects,
            stats,
            user_id=_current_user_id(),
            case_key=case_key,
            claimant_user_id=claimant_user_id,
            project_filter=project_filter,
        )

        # Keep boolean-like fields aligned with selected language before prompting AI.
        for item in report_data.get("defect_list", []):
            overdue_value = str(item.get("overdue", "")).strip().lower()
            hda_value = str(item.get("hda_compliance_30_days", "")).strip().lower()

            if language == "ms":
                item["overdue"] = "Ya" if overdue_value in {"yes", "ya"} else "Tidak"
                item["hda_compliance_30_days"] = "Ya" if hda_value in {"yes", "ya"} else "Tidak"
            else:
                item["overdue"] = "Yes" if overdue_value in {"yes", "ya"} else "No"
                item["hda_compliance_30_days"] = "Yes" if hda_value in {"yes", "ya"} else "No"

        report_data.setdefault("case_info", {})["item_service"] = _item_service_for_language(
            report_data.get("case_info", {}).get("item_service"),
            language,
        )
        
        # STEP 2: TRANSLATE STATUS BEFORE AI GENERATION
        for d in defects:
            if d.get("status"):
                d["status"] = STATUS_TRANSLATION.get(language, {}).get(
                    d["status"],
                    d["status"]
                )

        for d in report_data.get("defects", []):
            d["reported_date"] = d.get("reported_date", "-")
            d["deadline"] = d.get("deadline", "-")
            if d.get("status"):
                d["status"] = STATUS_TRANSLATION.get(language, {}).get(
                    d["status"],
                    d["status"]
                )

        report = generate_ai_report(role, report_data, language)

        versions = load_versions()
        role_versions = versions.get(role, [])
        new_version_number = len(role_versions)

        # FORCE STATUS LANGUAGE IN AI PREVIEW (REGEX SAFE)
        if language == "ms":
            status_ms = {
                'Reported': 'Dilaporkan',
                'WIP': 'Dalam Tindakan',
                'In Progress': 'Dalam Tindakan',
                'Done': 'Telah Diselesaikan',
                'Completed': 'Telah Diselesaikan',
                'Closed': 'Ditutup',
                'Pending': 'Belum Diselesaikan',
                'Delayed': 'Tertangguh'
            }
            for eng_status, ms_status in status_ms.items():
                report = re.sub(
                    rf"(Current Status|Status Semasa|Status)\s*:\s*{re.escape(eng_status)}",
                    rf"\g<1>: {ms_status}",
                    report,
                    flags=re.IGNORECASE
                )

            # Force overdue + HDA boolean wording to Bahasa Malaysia.
            report = re.sub(
                r"^\s*(Overdue Status|Status Tertunggak)\s*:\s*Yes\s*$",
                "Status Tertunggak: Ya",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(Overdue Status|Status Tertunggak)\s*:\s*No\s*$",
                "Status Tertunggak: Tidak",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(HDA Compliance \(30 Days\)|Pematuhan HDA \(30 Hari\))\s*:\s*Yes\s*$",
                "Pematuhan HDA (30 Hari): Ya",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(HDA Compliance \(30 Days\)|Pematuhan HDA \(30 Hari\))\s*:\s*No\s*$",
                "Pematuhan HDA (30 Hari): Tidak",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        else:
            # Force overdue + HDA boolean wording to English.
            report = re.sub(
                r"^\s*(Overdue Status|Status Tertunggak)\s*:\s*Ya\s*$",
                "Overdue Status: Yes",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(Overdue Status|Status Tertunggak)\s*:\s*(Tidak|No)\s*$",
                "Overdue Status: No",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(HDA Compliance \(30 Days\)|Pematuhan HDA \(30 Hari\))\s*:\s*Ya\s*$",
                "HDA Compliance (30 Days): Yes",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            report = re.sub(
                r"^\s*(HDA Compliance \(30 Days\)|Pematuhan HDA \(30 Hari\))\s*:\s*(Tidak|No)\s*$",
                "HDA Compliance (30 Days): No",
                report,
                flags=re.IGNORECASE | re.MULTILINE,
            )

        # PREPARE CORRECT CLAIM SUMMARY (BACKEND)
        summary = report_data.get("summary_stats", {})

        total_defects = summary.get("total_defects", 0)
        pending_count = summary.get("pending_defects", 0)
        completed_count = summary.get("completed_defects", 0)

        if language == "en":
            correct_summary = (
                "Claim Summary:\n"
                f"Total Defects Reported: {total_defects}\n"
                f"Pending: {pending_count}\n"
                f"Completed: {completed_count}"
            )
        else:
            correct_summary = (
                "Ringkasan Tuntutan:\n"
                f"Jumlah Kecacatan Dilaporkan: {total_defects}\n"
                f"Belum Diselesaikan: {pending_count}\n"
                f"Telah Diselesaikan: {completed_count}"
            )

        # import re
        # Replace ONLY the Claim Summary section in AI text
        report = re.sub(
            r"(Claim Summary:.*?)(?=\n[A-Z]|\Z)",
            correct_summary + "\n",
            report,
            flags=re.DOTALL
        )

        report = re.sub(
            r"(Ringkasan Tuntutan:.*?)(?=\n[A-Z]|\Z)",
            correct_summary + "\n",
            report,
            flags=re.DOTALL
        )

        # Keep section 1 (Case Background) aligned with backend/PDF values.
        case_info = report_data.get("case_info", {})
        report = enforce_case_background_section(
            report,
            language,
            case_info.get("claim_id"),
            case_info.get("claim_amount"),
            total_defects,
        )

        if role in ["Homeowner", "Developer", "Legal", "Admin"]:
            report = enforce_closed_appendix_format(report, closed_evidence_appendix, language)

        report = refresh_generated_datetime_line(report, language)

        # Validate AI report is not empty
        if not report or len(report.strip()) < 50:
            raise Exception("AI generated empty or insufficient report")

        # ==========================
        # SAVE REPORT VERSION (FINAL TEXT)
        # ==========================
        def _normalise_report_text(text):
            if not text:
                return ""
            text = re.sub(r"^Generated Date:\s.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"^Tarikh Jana:\s.*$", "", text, flags=re.MULTILINE)
            return text.strip()

        latest_same_language = None
        for item in reversed(role_versions):
            if item.get("language") == language:
                latest_same_language = item
                break

        if latest_same_language and _normalise_report_text(latest_same_language.get("report_text")) == _normalise_report_text(report):
            new_version_number = latest_same_language.get("version", len(role_versions))
        else:
            new_version_number = len(role_versions) + 1
            now_local = _now_app_timezone()

            role_versions.append({
                "version": new_version_number,
                "generated_at": now_local.strftime("%Y-%m-%d %H:%M:%S"),
                "language": language,
                "report_text": report
            })

            versions[role] = role_versions
            save_versions(versions)

        # AUDIT LOG: AI REPORT GENERATED
        _append_audit_event(
            action="AI Report Generated",
            role=role,
            details={
                "username": _current_actor_name(),
                "language": language,
                "version": new_version_number,
                "data_hash": data_hash,
                "defect_count": len(defects),
                "project_filter": project_filter or "All Projects",
            },
        )

        now_local = _now_app_timezone()

        return jsonify({
            "generated_at": now_local.strftime("%d/%m/%Y %H:%M:%S"),
            "role": role,
            "language": language,
            "report": report
        })

    except Exception as e:
        # DEBUG
        current_app.logger.error(f"AI Report Generation Failed: {str(e)}")
        
        # Provide more helpful error messages
        error_message = str(e)
        if "quota" in error_message.lower() or "429" in error_message:
            error_details = "API rate limit exceeded. Please try again later."
        elif "401" in error_message or "api_key" in error_message.lower():
            error_details = "API key invalid or missing. Check GROQ_API_KEY_REPORT or fallback GROQ_API_KEY."
        elif "timeout" in error_message.lower():
            error_details = "Request timed out. Please try again."
        else:
            error_details = str(e)

        return jsonify({
            "error": "Failed to generate AI report",
            "details": error_details,
            "debug": str(e) if current_app.debug else None
        }), 500

# =================================================
# EXPORT PDF - BORANG 1 TTPM FORMAT WITH AI REPORT
# PDF EXPORT ROUTE
# =================================================
@routes.route("/export_pdf", methods=["POST"])
@login_required
def export_pdf():
    role = _current_role()
    if role:
        role = role.strip().capitalize()
        if role == "Lawyer":
            role = "Legal"
            
    auto_close_completed_cases(trigger_role=role)
    backfill_missing_deadlines()
    # 🔒 Enforce backend role validation
    if role.lower() not in ["homeowner", "developer", "lawyer", "legal"]:
        return jsonify({"error": "Unauthorized role"}), 403
    language = _normalise_language(request.form.get("language", "ms"))
    ai_report_text = request.form.get("ai_report", "")
    project_filter = _normalise_project_filter_value(request.form.get("project_filter"))
    defects = get_defects_for_role(role)
    defects = filter_defects_by_project(defects, project_filter)
    
    if not defects:
        return jsonify(
            {
                "error": (
                    f"No defects found for project '{project_filter}'."
                    if project_filter
                    else "No defects available for PDF export."
                )
            }
        ), 400

    claimant_user_id = request.form.get("claimant_user_id", "")
    claimant_user_id = int(claimant_user_id) if str(claimant_user_id).strip().isdigit() else None

    claimant_user_id = _resolve_claimant_user_id(role, claimant_user_id, defects)
    if role == "Legal" and claimant_user_id is None:
        return jsonify(
            {
                "error": "No authorized homeowner selected for this lawyer.",
                "details": "This legal account can only export assigned cases.",
            }
        ), 403

    if role == "Legal" and claimant_user_id is not None:
        defects = [d for d in defects if d.get("user_id") == claimant_user_id]
        defects = filter_defects_by_project(defects, project_filter)
        if not defects:
            return jsonify(
                {
                    "error": "No assigned defects found for the selected homeowner.",
                    "details": "This legal account can only export assigned cases.",
                }
            ), 403

    if not ai_report_text or not ai_report_text.strip():
        return jsonify(
            {
                "error": "Please generate AI report before exporting PDF.",
            }
        ), 400

    requirement_errors = validate_report_requirements(role=role, user_id=_current_user_id(), claimant_user_id=claimant_user_id)
    if requirement_errors:
        return jsonify(
            {
                "error": "Cannot export PDF. Required profile/case data is incomplete.",
                "details": requirement_errors,
            }
        ), 400

    closed_evidence_appendix = get_closed_evidence_appendix(role, claimant_user_id=claimant_user_id)
    labels = PDF_LABELS.get(language, PDF_LABELS["ms"])
    remarks_store = load_remarks()
    status_store = load_status()
    completion_store = load_completion_dates()
    evidence_store = load_evidence()

    # LOAD DATA AND NORMALISE FIELDS
    for d in defects:
        # Load latest status from storage
        d["status"] = status_store.get(str(d["id"]), d["status"])

        d["completed_date"] = completion_store.get(
            str(d["id"]),
            d.get("completed_date")
        )
        d["closed"] = is_auto_closed(d["status"], d.get("completed_date"))
        d["display_status"] = "Closed" if d["closed"] else d["status"]

        evidence_data = evidence_store.get(str(d["id"]))
        if evidence_data:
            d["evidence_uploaded"] = True
            d["evidence_filename"] = evidence_data.get("filename")
            d["evidence_file_path"] = evidence_data.get("file_path")
        else:
            d["evidence_uploaded"] = False
            d["evidence_filename"] = None
            d["evidence_file_path"] = None

        d["hda_compliant"] = calculate_hda_compliance(
            d["reported_date"],
            d.get("completed_date"),
            d["status"]
        )

        d["is_overdue"] = calculate_overdue(
            d["deadline"],
            d.get("completed_date"),
            d["status"]
        )
        # Load remarks (Homeowner only, filtered later)
        d["remarks"] = remarks_store.get(str(d["id"]), "")

        # Normalise urgency → priority if priority is missing
        if "urgency" in d and not d.get("priority"):
            d["priority"] = d["urgency"]

    if role in ["Homeowner", "Developer", "Legal", "Admin"]:
        defects = [d for d in defects if not d.get("closed")]

    if not defects and not closed_evidence_appendix:
        return jsonify(
            {
                "error": (
                    f"No defects found for project '{project_filter}'."
                    if project_filter
                    else "No defects available for PDF export."
                )
            }
        ), 400

    # LOCK STATUS (BACKEND AUTHORITY)
    # Status must NEVER be modified by AI
    for d in defects:
        d["_status_raw"] = d["status"]  # Always English internally

    # TRANSLATE DEFECT TEXT (AI, CACHED)
    # Status is NOT translated here
    defects = translate_defects_cached(
        defects,
        language=language,
        role=role
    )

    # ==========================================
    # FORCE REMARK LANGUAGE FOR PDF
    # ==========================================
    for d in defects:
        if d.get("remarks"):
            d["remarks"] = translate_remark_cached(
                d["remarks"],
                language=language,
                role=role
            )

    # RESTORE ORIGINAL STATUS BEFORE STATS
    for d in defects:
        d["status"] = d.pop("_status_raw", d["status"])

    # =================================================
    # NORMALISE STATUS FOR STATISTICS (ALWAYS ENGLISH)
    # =================================================
    for d in defects:
        if d.get("status") in STATUS_NORMALISE:
            d["status"] = STATUS_NORMALISE[d["status"]]

    # CALCULATE STATISTICS (STATUS MUST BE ENGLISH)
    stats = calculate_stats(defects)
    preview_claim_id = extract_claim_reference_from_report_text(ai_report_text)
    case_key = build_case_key(role=role, user_id=claimant_user_id or _current_user_id(), defects=defects)
    report_data = build_report_data(
        role,
        defects,
        stats,
        user_id=_current_user_id(),
        case_key=case_key,
        claimant_user_id=claimant_user_id,
        forced_claim_number=preview_claim_id,
        project_filter=project_filter,
        closed_count=len(closed_evidence_appendix),
    )
    if preview_claim_id:
        report_data.setdefault("case_info", {})["claim_id"] = preview_claim_id
        report_data.setdefault("case_info", {})["claim_number"] = preview_claim_id
    report_data.setdefault("case_info", {})["item_service"] = _item_service_for_language(
        report_data.get("case_info", {}).get("item_service"),
        language,
    )

    # TRANSLATE STATUS FOR PDF DISPLAY ONLY
    for d in defects:
        if d.get("status"):
            d["status"] = STATUS_TRANSLATION.get(language, {}).get(
                d["status"],
                d["status"]
            )

    # HIDE REMARKS FOR NON-HOMEOWNER ROLES
    if role.lower() != "homeowner":
        for d in defects:
            d["remarks"] = ""

    # TRANSLATE PRIORITY FOR PDF DISPLAY
    for d in defects:
        if d.get("priority"):
            d["priority"] = PRIORITY_TRANSLATION.get(language, {}).get(
                d["priority"],
                d["priority"]
            )

    # Keep AI preview and exported PDF fully aligned by using the submitted preview text.

    if role in ["Homeowner", "Developer", "Legal", "Admin"]:
        ai_report_text = strip_closed_appendix_section(ai_report_text)

    # START PDF GENERATION
    # Generate PDF using service
    evidence_dir = os.path.join(current_app.root_path, "evidence")
    
    # Extract project_name from report_data to pass explicitly
    from app.models import User
    c_user_id = claimant_user_id or _current_user_id()
    c_user = User.query.get(c_user_id) if c_user_id else current_user
    
    # Use housing_project from the homeowner's profile if available
    project_name = getattr(c_user, 'housing_project', None)
    if not project_name or project_name.strip() in ["", "-"]:
        project_name = report_data.get("case_info", {}).get("project_name", "-")
    if not project_name or project_name.strip() in ["", "-"]:
        # Final fallback
        project_name = "Taman Desa Murni"
        
    report_data['project_name'] = project_name
    
    current_app.logger.info(f"DEBUG: Using project_name = {project_name} for PDF")
    
    buffer, filename = generate_tribunal_pdf(
        defects=defects,
        report_data=report_data,
        language=language,
        ai_report_text=ai_report_text,
        labels=labels,
        evidence_dir=evidence_dir,
        closed_evidence_appendix=closed_evidence_appendix,
        role=role,
        project_name_override=project_name,
    )
    
    # AUDIT LOG: PDF EXPORTED
    report_string = json.dumps(report_data, sort_keys=True)
    digital_hash = hashlib.sha256(report_string.encode()).hexdigest()
    
    _append_audit_event(
        action="PDF Exported",
        role=role,
        filename=filename,
        details={
            "username": _current_actor_name(),
            "language": language,
            "filename": filename,
            "hash": digital_hash,
        },
    )
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )



# --- Profile & Settings ---

@module3.route('/profile')
@login_required
def profile():
    return render_template('role/dashboard/profile.html', user=current_user)

@module3.route('/settings')
@login_required
def settings():
    import os
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    return render_template('role/dashboard/settings.html', user=current_user, google_maps_api_key=google_maps_api_key)

@module3.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    from ..extensions import db
    
    # 1. Update Email
    new_email = request.form.get('email', '').strip().lower()
    if new_email and new_email != current_user.email:
        # Check if email exists
        from ..models import User
        if User.query.filter(User.email == new_email, User.id != current_user.id).first():
            flash('This email is already in use.', 'error')
        else:
            current_user.email = new_email
            flash('Email updated successfully.', 'success')

    # 2. Update Profile Picture
    if 'profile_picture' in request.files:
        file = request.files['profile_picture']
        if file and file.filename != '' and allowed_file(file.filename):
            # Check file size (2MB limit)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > 2 * 1024 * 1024:
                flash('File size exceeds 2MB limit.', 'error')
            else:
                file.seek(0)
                filename = secure_filename(file.filename)
                unique_filename = f"user_{current_user.id}_{int(datetime.now().timestamp())}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)
                
                # Delete old profile picture if exists
                if current_user.profile_picture:
                    old_path = os.path.join(current_app.root_path, 'static', current_user.profile_picture)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                
                current_user.profile_picture = f"uploads/profiles/{unique_filename}"
                flash('Profile picture updated successfully.', 'success')
        elif file and file.filename != '':
            flash('Invalid file type. Only .jpg, .jpeg, .png are allowed.', 'error')

    # 3. Update Identity Card (IC / NRIC)
    new_ic = request.form.get('ic_number', '').strip()
    if new_ic:
        if current_user.user_type == 'developer':
            current_user.representative_nric = new_ic
        else:
            current_user.ic_number = new_ic

    # 4. Update Phone Number
    new_phone = request.form.get('phone_number', '').strip()
    if new_phone:
        current_user.phone_number = new_phone

    # 3b. Update IC Number
    new_ic = request.form.get('ic_number', '').strip()
    if new_ic:
        current_user.ic_number = new_ic

    # 4. Update Correspondence Address
    new_address = request.form.get('correspondence_address', '').strip()
    if new_address:
        current_user.correspondence_address = new_address

    # 6. Update Housing Project and Unit (For Homeowners)
    if current_user.user_type == 'homeowner':
        new_project = request.form.get('housing_project', '').strip()
        if new_project:
            current_user.housing_project = new_project
        
        new_unit = request.form.get('unit', '').strip()
        if new_unit:
            current_user.unit = new_unit

    db.session.commit()
    return redirect(url_for('module3.profile'))


@module3.route('/change_password', methods=['POST'])
@login_required
def change_password():
    from ..extensions import db
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')

    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('module3.settings'))

    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('module3.settings'))
    
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters long.', 'error')
        return redirect(url_for('module3.settings'))

    current_user.set_password(new_pw)
    db.session.commit()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('module3.profile'))
