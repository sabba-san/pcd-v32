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

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

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
from functools import wraps
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
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from config_pdf_labels import PDF_LABELS
    from report_data import (
        build_report_data,
        get_homeowner_claimants,
        validate_report_requirements,
    )
    from report_generator import generate_ai_report
# from prompts import get_language_config
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

SUPPORT_CONTACT = "1800-700-321 | support@dlp-project.edu.my"
SIMULATED_LOGIN_USER_ID = int(os.getenv("SIMULATED_LOGIN_USER_ID", "1"))
AUTO_CLOSE_DAYS = int(os.getenv("AUTO_CLOSE_DAYS", "14"))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")
ENABLE_DEMO_LOGIN_FALLBACK = os.getenv("ENABLE_DEMO_LOGIN_FALLBACK", "0") == "1"
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "120"))

DEMO_USERS = {
    "homeowner": {"password": "home123", "role": "Homeowner", "user_id": SIMULATED_LOGIN_USER_ID},
    "developer": {"password": "dev123", "role": "Developer", "user_id": None},
    "legal": {"password": "legal123", "role": "Legal", "user_id": None},
    "admin": {"password": "admin123", "role": "Admin", "user_id": None},
}

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


def _resolve_evidence_image_path(evidence_dir, defect_id, evidence_filename=None):
    if not evidence_dir or not os.path.isdir(evidence_dir):
        return None

    # 1) Try exact filename from metadata.
    candidate_name = (evidence_filename or "").strip()
    if candidate_name and candidate_name != "-":
        direct_candidate = os.path.join(evidence_dir, os.path.basename(candidate_name))
        if os.path.exists(direct_candidate):
            return direct_candidate

    # 2) Case-insensitive search by metadata basename.
    if candidate_name and candidate_name != "-":
        basename_lower = os.path.basename(candidate_name).lower()
        for fname in os.listdir(evidence_dir):
            if fname.lower() == basename_lower:
                full_path = os.path.join(evidence_dir, fname)
                if os.path.isfile(full_path):
                    return full_path

    # 3) Fallback by legacy defect_<id> naming, case-insensitive and any extension.
    prefix = f"defect_{defect_id}.".lower()
    for fname in os.listdir(evidence_dir):
        if fname.lower().startswith(prefix):
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
    return current_user.id if current_user.is_authenticated else None or (SIMULATED_LOGIN_USER_ID if ENABLE_DEMO_LOGIN_FALLBACK else None)


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
        else:
            password_valid = stored_password == password
            if password_valid:
                cur.execute(
                    "UPDATE login_accounts SET password = %s WHERE username = %s",
                    (generate_password_hash(password), row[0]),
                )
                conn.commit()

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
                       COALESCE(d.image_path, '') AS image_path
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
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
                       COALESCE(d.image_path, '') AS image_path
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
                WHERE d.assigned_lawyer_id = %s
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
                       COALESCE(d.image_path, '') AS image_path
                FROM defects d
                LEFT JOIN scans s ON d.scan_id = s.id
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

# AUTO BACKUP FUNCTION
def backup_versions():
    # Versions are persisted in the report_versions table.
    return None

def load_evidence():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT ON (defect_id) defect_id, filename, uploaded_at
            FROM evidence
            ORDER BY defect_id, uploaded_at DESC
            """
        )
        return {
            str(defect_id): {
                "filename": filename,
                "uploaded_at": str(uploaded_at),
            }
            for defect_id, filename, uploaded_at in cur.fetchall()
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
                "INSERT INTO evidence (defect_id, filename, uploaded_at) VALUES (%s, %s, %s)",
                (
                    int(defect_id),
                    item.get("filename"),
                    item.get("uploaded_at", _now_app_timezone().strftime("%Y-%m-%d %H:%M:%S")),
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
            appendix_lines.append(f"Tarikh Dilaporkan: {item.get('reported_date', '-')}")
            appendix_lines.append(f"Tarikh Siap: {item.get('completed_date', '-')}")
            appendix_lines.append(f"Tempoh Siap (Hari): {closed_days if closed_days is not None else '-'}")
            appendix_lines.append(f"Pematuhan HDA (30 Hari): {'Ya' if item.get('hda_compliant') else 'Tidak'}")
            appendix_lines.append(f"Peraturan Ditutup: Ditutup selepas {AUTO_CLOSE_DAYS} hari dari tarikh siap")
            appendix_lines.append(f"Muat Naik: {item.get('uploaded_at', '-')}")
            appendix_lines.append("Gambar Kecacatan: gambar")
        else:
            appendix_lines.append(f"{header_prefix} Defect ID {item.get('id', '-')}:")
            appendix_lines.append(f"Unit: {item.get('unit', '-')}")
            appendix_lines.append(f"Reported Date: {item.get('reported_date', '-')}")
            appendix_lines.append(f"Completed: {item.get('completed_date', '-')}")
            appendix_lines.append(f"Days to Complete: {closed_days if closed_days is not None else '-'}")
            appendix_lines.append(f"HDA Compliance (30 Days): {'Yes' if item.get('hda_compliant') else 'No'}")
            appendix_lines.append(f"Closed Rule: Closed after {AUTO_CLOSE_DAYS} days from completion")
            appendix_lines.append(f"Uploaded: {item.get('uploaded_at', '-')}")
            appendix_lines.append("Defect Image: image")

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
    
    auto_close_completed_cases(trigger_role=role)
    backfill_missing_deadlines()

    if role == "Admin":
        defects = get_defects_for_role("Developer")
        stats = calculate_stats(defects)
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

        conn.commit()
        return jsonify({"success": True, "message": "Claim details saved."})
    finally:
        cur.close()
        conn.close()


@routes.route("/debug/claim_state", methods=["GET"])
@login_required
def debug_claim_state():
    """Temporary debug route to inspect report metadata rows before generation."""
    def _serialize_row(columns, row):
        if not row:
            return None
        payload = {}
        for key, value in zip(columns, row):
            if hasattr(value, "isoformat"):
                payload[key] = value.isoformat()
            else:
                payload[key] = value
        return payload

    current_role = _current_role()
    role = current_role.capitalize() if current_role else "Homeowner"
    if role == "Lawyer":
        role = "Legal"

    user_id = _current_user_id()
    requirement_errors = validate_report_requirements(role=role, user_id=user_id, claimant_user_id=user_id)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT homeowner_id, name, ic_number, email, phone_number, address,
                   court_location, state_name, claim_amount, item_service,
                   transaction_date, updated_at
            FROM report_homeowner_profile
            WHERE homeowner_id = %s
            """,
            (user_id,),
        )
        homeowner_row = cur.fetchone()

        cur.execute(
            """
            SELECT respondent_id, company_name, registration_number, email,
                   phone_number, address, updated_at
            FROM report_respondent_profile
            WHERE homeowner_id = %s
            ORDER BY updated_at DESC, respondent_id ASC
            LIMIT 1
            """
            ,
            (user_id,),
        )
        first_respondent_row = cur.fetchone()

        cur.execute(
            """
            SELECT id, full_name, email, phone_number, unit, company_name, user_type
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user_row = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    return jsonify(
        {
            "debug_note": {
                "why_missing_data_happens": [
                    "HTML inputs may render but fail to map if the expected ids/names are missing or mismatched.",
                    "Frontend JS may submit an incomplete payload even when the form looks filled in.",
                    "Backend persistence may save only part of the claim profile, so later validation still sees missing DB columns.",
                ],
                "homeowner_report_rule": "Homeowner report generation validates the homeowner profile plus the respondent profile explicitly linked by homeowner_id.",
            },
            "request_context": {
                "current_user_id": user_id,
                "current_role": current_role,
                "normalized_role": role,
            },
            "user_row": _serialize_row(
                ["id", "full_name", "email", "phone_number", "unit", "company_name", "user_type"],
                user_row,
            ),
            "report_homeowner_profile": _serialize_row(
                [
                    "homeowner_id",
                    "name",
                    "ic_number",
                    "email",
                    "phone_number",
                    "address",
                    "court_location",
                    "state_name",
                    "claim_amount",
                    "item_service",
                    "transaction_date",
                    "updated_at",
                ],
                homeowner_row,
            ),
            "report_respondent_profile_linked_row": _serialize_row(
                [
                    "respondent_id",
                    "company_name",
                    "registration_number",
                    "email",
                    "phone_number",
                    "address",
                    "updated_at",
                ],
                first_respondent_row,
            ),
            "validation_errors": requirement_errors,
        }
    )

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

        # Create evidence directory if not exists
        evidence_dir = os.path.join(current_app.root_path, "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        
        # Get original extension
        ext = file.filename.rsplit('.', 1)[1].lower()

        filename = f"defect_{defect_id}.{ext}"
        filepath = os.path.join(evidence_dir, filename)

        file.save(filepath)

        # Save evidence metadata with timestamp
        now_local = _now_app_timezone()

        uploaded_at = now_local.strftime("%Y-%m-%d %H:%M:%S")

        evidence_img = load_evidence()
        evidence_img[defect_id] = {
            "filename": filename,
            "uploaded_at": uploaded_at
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
    from flask import send_from_directory
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
            "SELECT status, deadline FROM defects WHERE id = %s",
            (int(defect_id),),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Defect not found"}), 404

        old_status = row[0]
        old_deadline = _to_iso(row[1])

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
            report = re.sub(
                r"(Current Status|Status Semasa|Status)\s*:\s*Completed",
                "Status Semasa: Telah Diselesaikan",
                report,
                flags=re.IGNORECASE
            )
            report = re.sub(
                r"(Current Status|Status Semasa|Status)\s*:\s*Pending",
                "Status Semasa: Belum Diselesaikan",
                report,
                flags=re.IGNORECASE
            )
            report = re.sub(
                r"(Current Status|Status Semasa|Status)\s*:\s*In Progress",
                "Status Semasa: Dalam Tindakan",
                report,
                flags=re.IGNORECASE
            )
            report = re.sub(
                r"(Current Status|Status Semasa|Status)\s*:\s*Delayed",
                "Status Semasa: Tertangguh",
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
            backup_versions()

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
        else:
            d["evidence_uploaded"] = False
            d["evidence_filename"] = None

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
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Ensure evidence directory exists
    evidence_dir = os.path.join(current_app.root_path, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    # ============================================
    # PAGE 1: BORANG 1 HEADER & PARTIES
    # ============================================
    
    # --- HEADER (Centered) ---
    TOP_MARGIN = 40
    LINE_SPACING_SMALL = 13
    LINE_SPACING_MEDIUM = 16
    LINE_SPACING_LARGE = 22

    y = height - TOP_MARGIN

    # ---------------------------
    # ACT TITLE
    # ---------------------------
    pdf.setFont("Helvetica-Bold", 11)

    if language == "en":
        pdf.drawCentredString(width/2, y, "CONSUMER PROTECTION ACT 1999")
    else:
        pdf.drawCentredString(width/2, y, "AKTA PERLINDUNGAN PENGGUNA 1999")

    y -= LINE_SPACING_MEDIUM


    # ---------------------------
    # REGULATIONS TITLE
    # ---------------------------
    pdf.setFont("Helvetica-Bold", 10)

    if language == "en":
        pdf.drawCentredString(width/2, y, "CONSUMER PROTECTION REGULATIONS")
    else:
        pdf.drawCentredString(width/2, y, "PERATURAN-PERATURAN PERLINDUNGAN PENGGUNA")

    y -= LINE_SPACING_SMALL


    # ---------------------------
    # TRIBUNAL REFERENCE
    # ---------------------------
    if language == "en":
        pdf.drawCentredString(width/2, y, "(CONSUMER CLAIMS TRIBUNAL) 1999")
    else:
        pdf.drawCentredString(width/2, y, "(TRIBUNAL TUNTUTAN PENGGUNA) 1999")

    y -= LINE_SPACING_LARGE


    # ---------------------------
    # FORM TITLE
    # ---------------------------
    pdf.setFont("Helvetica-Bold", 12)

    if language == "en":
        pdf.drawCentredString(width/2, y, "FORM 1")
    else:
        pdf.drawCentredString(width/2, y, "BORANG 1")

    y -= LINE_SPACING_SMALL


    pdf.setFont("Helvetica", 9)

    if language == "en":
        pdf.drawCentredString(width/2, y, "(Regulation 5)")
    else:
        pdf.drawCentredString(width/2, y, "(Peraturan 5)")

    y -= LINE_SPACING_LARGE


    # ---------------------------
    # STATEMENT TITLE
    # ---------------------------
    pdf.setFont("Helvetica-Bold", 11)

    if language == "en":
        pdf.drawCentredString(width/2, y, "STATEMENT OF CLAIM")
    else:
        pdf.drawCentredString(width/2, y, "PERNYATAAN TUNTUTAN")

    y -= LINE_SPACING_MEDIUM


    pdf.setFont("Helvetica", 10)

    if language == "en":
        pdf.drawCentredString(width/2, y, "IN THE CONSUMER CLAIMS TRIBUNAL")
    else:
        pdf.drawCentredString(width/2, y, "DALAM TRIBUNAL TUNTUTAN PENGGUNA")

    y -= 16


    # ============================================
    # LOCATION & CLAIM NUMBER
    # ============================================

    pdf.setFont("Helvetica", 10)

    lokasi = str(report_data["case_info"].get("tribunal_location") or "-").strip().upper()
    negeri = str(report_data["case_info"].get("state_name") or "-").strip().upper()
    no_tuntutan = report_data["case_info"].get("claim_number") or "-"
    project_name = report_data["case_info"].get("project_name") or "-"

    if language == "en":
        pdf.drawCentredString(width/2, y, f"AT {lokasi}")
        y -= LINE_SPACING_MEDIUM

        pdf.drawCentredString(width/2, y, f"IN THE STATE OF {negeri}, MALAYSIA")
        y -= LINE_SPACING_LARGE

        pdf.drawString(50, y, f"CLAIM NO.: {no_tuntutan}")
    else:
        pdf.drawCentredString(width/2, y, f"DI {lokasi}")
        y -= LINE_SPACING_MEDIUM

        pdf.drawCentredString(width/2, y, f"DI NEGERI {negeri}, MALAYSIA")
        y -= LINE_SPACING_LARGE

        pdf.drawString(50, y, f"TUNTUTAN NO.: {no_tuntutan}")

    y -= 18
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, f"PROJECT / TAMAN: {project_name}")
    else:
        pdf.drawString(50, y, f"PROJEK / TAMAN: {project_name}")

    y -= 20

    # --- PIHAK YANG MENUNTUT (Claimant) ---
    y -= 20
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "CLAIMANT")
    else:
        pdf.drawString(50, y, "PIHAK YANG MENUNTUT")
    
    # Draw box for claimant details
    box_x = 50
    box_y = y - 120
    box_width = width - 100
    box_height = 110
    pdf.rect(box_x, box_y, box_width, box_height)
    
    # Claimant form fields
    y -= 20
    pdf.setFont("Helvetica", 9)
    claimant = report_data['claimant']
    
    # Enforce claimant name from current_user (Homeowner scenario)
    claimant_name = current_user.full_name if current_user.is_authenticated and _current_role_key() == "homeowner" else claimant.get('name', '')

    if language == "en":
        pdf.drawString(60, y, "Claimant Name")
        pdf.drawString(200, y, f": {claimant_name}")
        y -= 18
        pdf.drawString(60, y, "IC/Passport No.")
        # Encrypt NRIC before displaying (simulation of encryption at rest)
        encrypted_nric = encrypt_text(claimant.get('national_id', ''))
        decrypted_nric = decrypt_text(encrypted_nric)

        pdf.drawString(200, y, f": {decrypted_nric}")
        y -= 18
        pdf.drawString(60, y, "Correspondence Address")
        claimant_address = str(claimant.get('address_line_1') or '-').strip()
        pdf.drawString(200, y, f": {claimant_address}")
        y -= 18
        pdf.drawString(60, y, "Phone No.")
        pdf.drawString(200, y, f": {claimant.get('phone_number', '')}")
        y -= 18
        pdf.drawString(60, y, "Fax/Email")
        pdf.drawString(200, y, f": {claimant.get('email', '')}")
    else:
        pdf.drawString(60, y, "Nama Pihak Yang Menuntut")
        pdf.drawString(200, y, f": {claimant_name}")
        y -= 18
        pdf.drawString(60, y, "No. Kad Pengenalan/Pasport")
        # Encrypt NRIC before displaying (simulation of encryption at rest)
        encrypted_nric = encrypt_text(claimant.get('national_id', ''))
        decrypted_nric = decrypt_text(encrypted_nric)

        pdf.drawString(200, y, f": {decrypted_nric}")
        y -= 18
        pdf.drawString(60, y, "Alamat Surat Menyurat")
        claimant_address = str(claimant.get('address_line_1') or '-').strip()
        pdf.drawString(200, y, f": {claimant_address}")
        y -= 18
        pdf.drawString(60, y, "No. Telefon")
        pdf.drawString(200, y, f": {claimant.get('phone_number', '')}")
        y -= 18
        pdf.drawString(60, y, "No. Faks/ E-mel")
        pdf.drawString(200, y, f": {claimant.get('email', '')}")
    
    # --- PENENTANG (Respondent/Developer) ---
    y -= 45
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "RESPONDENT")
    else:
        pdf.drawString(50, y, "PENENTANG")
    
    # Draw box for respondent details - make it taller to fit all content
    box_top = y - 10
    box_height = 190
    pdf.rect(box_x, box_top - box_height, box_width, box_height)
    
    # Respondent form fields
    y -= 22
    pdf.setFont("Helvetica", 9)
    respondent = report_data['respondent']
    if language == "en":
        pdf.drawString(60, y, "Name of Respondent/Company/")
        pdf.drawString(200, y, f": {respondent.get('name', '')}")
        y -= 12
        pdf.drawString(60, y, "Corporation/Organisation/Firm")
        y -= 18

        pdf.drawString(60, y, "Identity Card No./")
        pdf.drawString(200, y, f": {respondent.get('registration_no', '')}")
        y -= 12
        pdf.drawString(60, y, "Company Registration No./")
        y -= 12
        pdf.drawString(60, y, "Corporation/Organisation/Firm")
        y -= 18

        pdf.drawString(60, y, "Correspondence Address")
        pdf.drawString(200, y, f": {respondent.get('address_line_1', '')}")
        y -= 16

        pdf.drawString(60, y, "Telephone No.")
        pdf.drawString(200, y, f": {respondent.get('phone_number', '')}")
        y -= 16

        pdf.drawString(60, y, "Fax/E-mail")
        pdf.drawString(200, y, f": {respondent.get('email', '')}")
    else:
        pdf.drawString(60, y, "Nama Penentang/Syarikat/")
        pdf.drawString(200, y, f": {respondent.get('name', '')}")
        y -= 12
        pdf.drawString(60, y, "Pertubuhan Perbadanan/Firma")
        y -= 18
        pdf.drawString(60, y, "No. Kad Pengenalan/")
        pdf.drawString(200, y, f": {respondent.get('registration_no', '')}")
        y -= 12
        pdf.drawString(60, y, "No. Pendaftaran Syarikat/")
        y -= 12
        pdf.drawString(60, y, "Pertubuhan Perbadanan/Firma")
        y -= 18
        pdf.drawString(60, y, "Alamat Surat Menyurat")
        pdf.drawString(200, y, f": {respondent.get('address_line_1', '')}")
        y -= 16
        pdf.drawString(60, y, "No. Telefon")
        pdf.drawString(200, y, f": {respondent.get('phone_number', '')}")
        y -= 16
        pdf.drawString(60, y, "No. Faks/E-mel")
        pdf.drawString(200, y, f": {respondent.get('email', '')}")

    # Move y below the PENENTANG box
    y = box_top - box_height - 30
    
    # --- PERNYATAAN TUNTUTAN (Claim Amount) - on same page ---
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "STATEMENT OF CLAIM")
        y -= 20
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, "The Claimant's claim is for the amount of RM:")
        claim_amt = str(report_data['case_info'].get('claim_amount') or '-').replace('RM', '').strip()
        pdf.drawString(280, y, f": {claim_amt}")
    else:
        pdf.drawString(50, y, "PERNYATAAN TUNTUTAN")
        y -= 20
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, "Tuntutan Pihak Yang Menuntut ialah untuk jumlah RM:")
        claim_amt = str(report_data['case_info'].get('claim_amount') or '-').replace('RM', '').strip()
        pdf.drawString(280, y, f": {claim_amt}")
    
    # --- BUTIR-BUTIR TUNTUTAN (Claim Details) ---
    y -= 30
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Claim Details")
    else:
        pdf.drawString(50, y, "Butir-butir Tuntutan")
    
    # Draw box for claim details - box starts below title
    box_top = y - 10
    box_height = 75
    pdf.rect(50, box_top - box_height, width - 100, box_height)
    
    y -= 20
    pdf.setFont("Helvetica", 9)
    if language == "en":
        pdf.drawString(60, y, "Goods/Services")
        pdf.drawString(200, y, f": {report_data['case_info'].get('item_service', 'Defect Repairs During DLP Period')}")
        y -= 15
        pdf.drawString(60, y, "Date of Purchase/Transaction")
        pdf.drawString(200, y, f": {report_data['case_info'].get('transaction_date', report_data['case_info']['generated_date'])}")
        y -= 15
        pdf.drawString(60, y, "Amount Paid")
        pdf.drawString(200, y, f": RM {report_data['case_info'].get('claim_amount', '-')}")
        y -= 15
        pdf.drawString(60, y, "Property Location")
        pdf.drawString(200, y, f": {report_data['case_info'].get('project_name', '-')}")
    else:
        pdf.drawString(60, y, "Barangan/Perkhidmatan")
        pdf.drawString(200, y, f": {report_data['case_info'].get('item_service', 'Pembaikan Kecacatan Dalam Tempoh DLP')}")
        y -= 15
        pdf.drawString(60, y, "Tarikh Pembelian/ Transaksi")
        pdf.drawString(200, y, f": {report_data['case_info'].get('transaction_date', report_data['case_info']['generated_date'])}")
        y -= 15
        pdf.drawString(60, y, "Jumlah yang dibayar")
        pdf.drawString(200, y, f": RM {report_data['case_info'].get('claim_amount', '-')}")
        y -= 15
        pdf.drawString(60, y, "Lokasi Harta")
        pdf.drawString(200, y, f": {report_data['case_info'].get('project_name', '-')}")

    # ============================================
    # PAGE 2: RINGKASAN & SENARAI KECACATAN
    # ============================================
    draw_footer(pdf, width, labels)
    pdf.showPage()
    y = height - 50
    
    # --- RINGKASAN TUNTUTAN (Claim Summary) ---
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Claim Summary:")
    else:
        pdf.drawString(50, y, "Ringkasan Tuntutan:")
    
    # Draw box for claim summary
    box_top = y - 10
    box_height = 100
    pdf.rect(50, box_top - box_height, width - 100, box_height)
    
    # Summary statistics inside the box
    y -= 25
    pdf.setFont("Helvetica", 9)
    summary = report_data['summary_stats']
    if language == "en":
        pdf.drawString(60, y, f"Total Defects Reported: {summary['total_defects']}")
        y -= 15
        pdf.drawString(60, y, f"Pending: {summary['pending_defects']}")
        y -= 15
        pdf.drawString(60, y, f"In Progress: {summary.get('investigation_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Completed: {summary['completed_defects']}")
        y -= 15
        pdf.drawString(60, y, f"Overdue: {summary.get('overdue_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Non-Compliant (30-Day HDA): {summary.get('hda_non_compliant_defects', 0)}")
        y -= 15
    else:
        pdf.drawString(60, y, f"Jumlah Kecacatan Dilaporkan: {summary['total_defects']}")
        y -= 15
        pdf.drawString(60, y, f"Belum Diselesaikan: {summary['pending_defects']}")
        y -= 15
        pdf.drawString(60, y, f"Dalam Tindakan: {summary.get('investigation_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Telah Diselesaikan: {summary['completed_defects']}")
        y -= 15
        pdf.drawString(60, y, f"Telah Melebihi Tarikh Siap: {summary.get('overdue_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Tidak Mematuhi Tempoh 30 Hari: {summary.get('hda_non_compliant_defects', 0)}")
        y -= 15
    # Move y below the box
    y = box_top - box_height - 20

    if role in ["Homeowner", "Developer", "Legal"] and closed_evidence_appendix:
        pdf.setFont("Helvetica-Oblique", 8)
        if language == "en":
            y = draw_wrapped_text(
                pdf,
                "Note: Closed cases are excluded from the main defect summary and listed in Appendix A. This rule is applied consistently across Homeowner, Developer, and Legal roles.",
                50,
                y,
                width - 100,
                "Helvetica-Oblique",
                8,
                12,
            )
        else:
            y = draw_wrapped_text(
                pdf,
                "Nota: Kes berstatus Ditutup dikecualikan daripada ringkasan utama dan disenaraikan dalam Lampiran A. Peraturan ini digunakan secara konsisten bagi peranan Homeowner, Developer dan Legal.",
                50,
                y,
                width - 100,
                "Helvetica-Oblique",
                8,
                12,
            )
        y -= 6
    
    # --- SENARAI KECACATAN (Defect List) ---
    y -= 35
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Defect List:")
    else:
        pdf.drawString(50, y, "Senarai Kecacatan:")
    
    y -= 20
    pdf.setFont("Helvetica", 9)

    def _estimate_wrapped_lines_with_font(text, font_name, font_size, max_width):
        words = str(text or "").split()
        if not words:
            return 1

        line = ""
        line_count = 0
        for word in words:
            candidate = f"{line} {word}" if line else word
            if pdf.stringWidth(candidate, font_name, font_size) <= max_width:
                line = candidate
            else:
                line_count += 1
                line = word
        if line:
            line_count += 1
        return max(line_count, 1)
    
    for i, defect in enumerate(defects, 1):

        # ===============================
        # CONSISTENT INDENT POSITIONS
        # ===============================
        HEADER_X = 50      # a. Kecacatan ID
        LABEL_X  = 70      # Keterangan / Unit / Status
        VALUE_X  = 220     # isi selepas :
        RIGHT_MARGIN = 50
        TEXT_WIDTH = width - VALUE_X - RIGHT_MARGIN

        # Keep a full defect block together when possible.
        desc_lines = _estimate_wrapped_lines_with_font(f": {defect.get('desc', '-')}", "Helvetica", 9, TEXT_WIDTH)
        remarks_lines = 0
        if role == "Homeowner" and defect.get("remarks"):
            remarks_lines = _estimate_wrapped_lines_with_font(f": {defect.get('remarks', '')}", "Helvetica", 9, TEXT_WIDTH)

        hda_message = (
            "Rectified within thirty (30) days from date of notification pursuant to HDA"
            if language == "en" and defect.get("hda_compliant")
            else "Failed to Comply with 30-Day Requirement under HDA"
            if language == "en"
            else "Diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"
            if defect.get("hda_compliant")
            else "Tidak diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"
        )
        hda_lines = _estimate_wrapped_lines_with_font(f": {hda_message}", "Helvetica", 9, TEXT_WIDTH)

        image_path_for_height = _resolve_evidence_image_path(
            evidence_dir,
            defect.get("id"),
            defect.get("evidence_filename"),
        )

        estimated_height = 0
        estimated_height += 16                              # defect header
        estimated_height += desc_lines * 14                # description
        estimated_height += 14 * 7                         # unit/status/reported/deadline/actual/days/overdue lines
        estimated_height += hda_lines * 14                 # HDA line (wrapped)
        if defect.get("priority"):
            estimated_height += 14
        if remarks_lines > 0:
            estimated_height += remarks_lines * 14
        if image_path_for_height:
            estimated_height += 140                        # evidence label+image+uploaded time spacing
        estimated_height += 25                             # space between defects

        # Ensure enough space for ONE full defect block
        if y - estimated_height < 80:
            draw_footer(pdf, width, labels)
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica-Bold", 10)
            if language == "en":
                pdf.drawString(50, y, "Defect List (continued):")
            else:
                pdf.drawString(50, y, "Senarai Kecacatan (sambungan):")
            y -= 30

        # ===== DEFECT HEADER =====
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(
            HEADER_X,
            y,
            f"{chr(64+i)}. {labels['defect_id']} {defect['id']}:"
        )
        y -= 16

        pdf.setFont("Helvetica", 9)

        # ---- Keterangan ----
        desc_text = defect['desc']
        pdf.drawString(LABEL_X, y, labels["description"])
        y = draw_wrapped_text(
            pdf,
            f": {desc_text}",
            VALUE_X,
            y,
            TEXT_WIDTH
        )

        # ---- Unit ----
        pdf.drawString(LABEL_X, y, labels["unit"])
        pdf.drawString(VALUE_X, y, f": {defect['unit']}")
        y -= 14

        # ---- Status ----
        pdf.drawString(LABEL_X, y, labels["status"])
        status_text = defect["status"]
        pdf.drawString(VALUE_X, y, f": {status_text}")
        y -= 14

        # ---- Reported Date ----
        pdf.drawString(LABEL_X, y, labels.get("reported_date", "Reported Date"))
        pdf.drawString(VALUE_X, y, f": {defect.get('reported_date', '-')}")
        y -= 14


        # ---- Scheduled Completion Date ----
        pdf.drawString(LABEL_X, y, labels.get("deadline", "Scheduled Completion Date"))
        pdf.drawString(VALUE_X, y, f": {defect.get('deadline', '-')}")
        y -= 14

        # ---- Actual Completion Date ----
        pdf.drawString(LABEL_X, y, labels.get("actual_completion_date", "Actual Completion Date"))
        pdf.drawString(VALUE_X, y, f": {defect.get('completed_date') if defect.get('completed_date') else '-'}")
        y -= 14

        # ---- Days to Complete ----
        days_to_complete = calculate_days_to_complete(
            defect.get("reported_date"),
            defect.get("completed_date"),
        )
        if language == "en":
            pdf.drawString(LABEL_X, y, "Days to Complete")
            pdf.drawString(VALUE_X, y, f": {days_to_complete if days_to_complete is not None else '-'}")
        else:
            pdf.drawString(LABEL_X, y, "Tempoh Siap (Hari)")
            pdf.drawString(VALUE_X, y, f": {days_to_complete if days_to_complete is not None else '-'}")
        y -= 14

        # ---- HDA Compliance ----
        pdf.setFont("Helvetica", 9)

        if language == "en":
            pdf.drawString(LABEL_X, y, "HDA Compliance (30 Days)")
            if defect.get("hda_compliant"):
                message = "Rectified within thirty (30) days from date of notification pursuant to HDA"
            else:
                message = "Failed to Comply with 30-Day Requirement under HDA"
        else:
            pdf.drawString(LABEL_X, y, "Pematuhan HDA (30 Hari)")
            if defect.get("hda_compliant"):
                message = "Diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"
            else:
                message = "Tidak diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"

        pdf.drawString(VALUE_X, y, f": {message}")
        y -= 14

        # ---- Overdue ----
        pdf.setFont("Helvetica", 9)

        is_overdue = defect.get("is_overdue", False)

        if language == "en":
            pdf.drawString(LABEL_X, y, "Overdue")
            pdf.drawString(VALUE_X, y, f": {'Yes' if is_overdue else 'No'}")
        else:
            pdf.drawString(LABEL_X, y, "Melebihi Tarikh")
            pdf.drawString(VALUE_X, y, f": {'Ya' if is_overdue else 'Tidak'}")

        y -= 14

        # ---- Keutamaan (jika ada) ----
        if defect.get("priority"):
            pdf.drawString(LABEL_X, y, labels["priority"])
            pdf.drawString(VALUE_X, y, f": {defect['priority']}")
            y -= 14

        # ---- Ulasan (Homeowner sahaja) ----
        if role == "Homeowner" and defect.get("remarks"):
            pdf.drawString(LABEL_X, y, labels["remarks"])
            y = draw_wrapped_text(
                pdf,
                f": {defect['remarks']}",
                VALUE_X,
                y,
                TEXT_WIDTH
            )

        # ---- Bukti Kecacatan ----
        image_path = _resolve_evidence_image_path(
            evidence_dir,
            defect.get("id"),
            defect.get("evidence_filename"),
        )

        # If evidence exists → draw it
        if image_path:

            if y < 180:
                draw_footer(pdf, width, labels)
                pdf.showPage()
                y = height - 50

            pdf.setFont("Helvetica-Oblique", 8)
            pdf.drawString(LABEL_X, y, f"{labels['evidence']}:")
            y -= 10

            pdf.drawImage(
                ImageReader(image_path),
                LABEL_X,
                y - 110,
                width=200,
                height=110
            )

            y -= 125

            # EVIDENCE UPLOAD TIMESTAMP
            evidence_img = load_evidence()
            upload_time = evidence_img.get(str(defect['id']), {}).get("uploaded_at", "-")

            pdf.setFont("Helvetica", 8)

            if language == "en":
                pdf.drawString(LABEL_X, y - 5, f"Uploaded At: {upload_time}")
            else:
                pdf.drawString(LABEL_X, y - 5, f"Tarikh Muat Naik: {upload_time}")

            y -= 15

        # Space between defects
        y -= 25

    # ============================================
    # AI REPORT SECTION (Ringkasan Tuntutan)
    # ============================================
    if ai_report_text:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50

        # Margins & spacing
        LEFT_MARGIN = 50
        PARAGRAPH_INDENT = 70
        RIGHT_MARGIN = width - 50
        LINE_HEIGHT = 18
        TEXT_WIDTH = RIGHT_MARGIN - PARAGRAPH_INDENT

        # AI Report Header
        pdf.setFont("Helvetica-Bold", 12)
        if language == "en":
            pdf.drawCentredString(width/2, y, "AI-GENERATED CLAIM SUMMARY REPORT")
        else:
            pdf.drawCentredString(width/2, y, "LAPORAN RINGKASAN TUNTUTAN DIJANA AI")

        y -= 30

        # Clean AI report text
        import re
        clean_text = ai_report_text
        summary = report_data.get("summary_stats", {})

        clean_text = re.sub(
            r"Total number of defects.*?\.",
            f"Total number of defects reported is {summary.get('total_defects',0)}.",
            clean_text
        )
        clean_text = clean_text.replace('**', '')
        clean_text = clean_text.replace('*', '')
        clean_text = clean_text.replace('##', '')
        clean_text = clean_text.replace('#', '')
        clean_text = clean_text.replace('\r\n', '\n')
        clean_text = clean_text.replace('\r', '\n')
        clean_text = clean_text.encode("utf-8", "ignore").decode("utf-8")
        # TRANSLATE STATUS/OVERDUE/HDA/PRIORITY INSIDE AI REPORT TEXT
        if language == "en":
            clean_text = clean_text.replace("Status: Telah Diselesaikan", "Status: Completed")
            clean_text = clean_text.replace("Status: Belum Diselesaikan", "Status: Pending")
            clean_text = clean_text.replace("Status: Dalam Tindakan", "Status: In Progress")
            clean_text = clean_text.replace("Status: Tertangguh", "Status: Delayed")

            clean_text = clean_text.replace("Status Tertunggak:", "Overdue Status:")
            clean_text = clean_text.replace("Pematuhan HDA (30 Hari):", "HDA Compliance (30 Days):")

            clean_text = re.sub(r"^\s*Overdue\s*Status\s*:\s*Ya\s*$", "Overdue Status: Yes", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*Overdue\s*Status\s*:\s*(Tidak|No)\s*$", "Overdue Status: No", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*HDA\s*Compliance\s*\(30\s*Days\)\s*:\s*Ya\s*$", "HDA Compliance (30 Days): Yes", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*HDA\s*Compliance\s*\(30\s*Days\)\s*:\s*(Tidak|No)\s*$", "HDA Compliance (30 Days): No", clean_text, flags=re.IGNORECASE | re.MULTILINE)

            clean_text = clean_text.replace("Keutamaan:", "Priority:")
            clean_text = clean_text.replace("Priority: Tinggi", "Priority: High")
            clean_text = clean_text.replace("Priority: Sederhana", "Priority: Medium")
            clean_text = clean_text.replace("Priority: Rendah", "Priority: Low")
        else:
            clean_text = clean_text.replace("Status: Completed", "Status: Telah Diselesaikan")
            clean_text = clean_text.replace("Status: Pending", "Status: Belum Diselesaikan")
            clean_text = clean_text.replace("Status: In Progress", "Status: Dalam Tindakan")
            clean_text = clean_text.replace("Status: Delayed", "Status: Tertangguh")

            clean_text = clean_text.replace("Status Semasa: Completed", "Status Semasa: Telah Diselesaikan")
            clean_text = clean_text.replace("Status Semasa: Pending", "Status Semasa: Belum Diselesaikan")
            clean_text = clean_text.replace("Status Semasa: In Progress", "Status Semasa: Dalam Tindakan")
            clean_text = clean_text.replace("Status Semasa: Delayed", "Status Semasa: Tertangguh")

            clean_text = clean_text.replace("Current Status: Completed", "Status Semasa: Telah Diselesaikan")
            clean_text = clean_text.replace("Current Status: Pending", "Status Semasa: Belum Diselesaikan")
            clean_text = clean_text.replace("Current Status: In Progress", "Status Semasa: Dalam Tindakan")
            clean_text = clean_text.replace("Current Status: Delayed", "Status Semasa: Tertangguh")

            clean_text = clean_text.replace("Overdue Status:", "Status Tertunggak:")
            clean_text = clean_text.replace("HDA Compliance (30 Days):", "Pematuhan HDA (30 Hari):")

            clean_text = re.sub(r"^\s*Status\s*Tertunggak\s*:\s*Yes\s*$", "Status Tertunggak: Ya", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*Status\s*Tertunggak\s*:\s*No\s*$", "Status Tertunggak: Tidak", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*Pematuhan\s*HDA\s*\(30\s*Hari\)\s*:\s*Yes\s*$", "Pematuhan HDA (30 Hari): Ya", clean_text, flags=re.IGNORECASE | re.MULTILINE)
            clean_text = re.sub(r"^\s*Pematuhan\s*HDA\s*\(30\s*Hari\)\s*:\s*No\s*$", "Pematuhan HDA (30 Hari): Tidak", clean_text, flags=re.IGNORECASE | re.MULTILINE)

            clean_text = clean_text.replace("Priority:", "Keutamaan:")
            clean_text = clean_text.replace("Keutamaan: High", "Keutamaan: Tinggi")
            clean_text = clean_text.replace("Keutamaan: Medium", "Keutamaan: Sederhana")
            clean_text = clean_text.replace("Keutamaan: Low", "Keutamaan: Rendah")

        # =================================================
        # FIX REMARKS LANGUAGE USING DEFECT DATA (AUTHORITATIVE)
        # =================================================
        if language == "ms":
            for defect in defects:
                if defect.get("remarks"):
                    clean_text = clean_text.replace(
                        "Ulasan:",
                        "Ulasan:"
                    )

        elif language == "en":
            for defect in defects:
                if defect.get("remarks"):
                    clean_text = clean_text.replace(
                        "Remarks:",
                        "Remarks:"
                    )

        # Split AI report into lines
        lines = clean_text.split('\n')

        MAIN_SECTION_HEADER_PREFIXES = (
            'PENAFIAN AI',
            'Penafian AI',
            'AI Disclaimer',
            'Laporan Sokongan',
            'Laporan Pematuhan',
            'Laporan Gambaran',
            'Purpose of the Report',
            'Summary of Reported Defects',
            'Defect List',
            'Defects That Have Exceeded',
            'Formal Request',
            'Conclusion',
            'Tribunal Support Report',
        )

        def _estimate_wrapped_lines(text, max_width):
            words = text.split()
            if not words:
                return 1

            count = 0
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if pdf.stringWidth(test_line, "Helvetica", 9) <= max_width:
                    current_line = test_line
                else:
                    count += 1
                    current_line = word
            if current_line:
                count += 1
            return max(count, 1)

        def _is_main_section_header(text):
            if not text:
                return False

            if re.match(r"^\d+\.\s", text):
                return True

            return text.startswith(MAIN_SECTION_HEADER_PREFIXES)

        def _is_subtopic_header(text):
            if not text:
                return False
            return bool(re.match(r"^[A-Za-z]\.\s", text))

        def _is_keep_together_header(text):
            return _is_main_section_header(text) or _is_subtopic_header(text)

        prev_line_is_sub_item = False

        for idx, line in enumerate(lines):
            # Empty line spacing
            if not line.strip():
                y -= 8
                prev_line_is_sub_item = False
                continue

            # Page break
            if y < 80:
                draw_footer(pdf, width, labels)
                pdf.showPage()
                y = height - 50

            stripped = line.strip()

            # Keep each header/subtopic block together when possible.
            if _is_keep_together_header(stripped):
                block_end = len(lines)
                for j in range(idx + 1, len(lines)):
                    nxt = lines[j].strip()
                    if _is_keep_together_header(nxt):
                        block_end = j
                        break

                required_height = 0
                for j in range(idx, block_end):
                    candidate = lines[j].strip()
                    if not candidate:
                        required_height += 8
                    else:
                        wrapped_count = _estimate_wrapped_lines(candidate, TEXT_WIDTH)
                        required_height += wrapped_count * LINE_HEIGHT

                page_usable_height = (height - 50) - 80
                if required_height <= page_usable_height and y - required_height < 80:
                    draw_footer(pdf, width, labels)
                    pdf.showPage()
                    y = height - 50

            # -----------------------------------------
            # FORMAL SPACING RULES (TRIBUNAL-GRADE)
            # -----------------------------------------

            # Extra space before numbered sections (2., 3., etc.)
            if re.match(r"^\d+\.\s", stripped):
                y -= 12   # space before new main section

            # Extra space before lettered items (A., B., C.)
            if stripped[:2] in ["A.", "B.", "C.", "D.", "E.", "F."]:
                y -= 8    # space before each defect item

            # Detect headers (LEFT ALIGN ONLY)
            is_numbered_header = _is_main_section_header(stripped)

            lower_line = stripped.lower()
            SUB_ITEM_PREFIXES = tuple(f"{chr(i)}." for i in range(ord('a'), ord('z') + 1))
            is_sub_item = lower_line.startswith(SUB_ITEM_PREFIXES)

            # Defect detail fields
            BASE_FIELDS = (
                "unit:",
                "status:",
            )

            MS_FIELDS = (
                "keterangan:",
                "keutamaan:",
                "ulasan:",
                "tarikh dilaporkan:",
                "tarikh siap dijadualkan:",
                "tarikh siap:",
                "tarikh siap sebenar:",
                "tempoh siap (hari):",
                "status tertunggak:",
                "status semasa:",
                "pematuhan hda (30 hari):",
            )

            EN_FIELDS = (
                "description:",
                "priority:",
                "remarks:",
                "reported date:",
                "scheduled completion date:",
                "actual completion date:",
                "days to complete:",
                "current status:",
                "overdue status:",
                "hda compliance (30 days):",
            )

            DEFECT_FIELD_PREFIXES = BASE_FIELDS + MS_FIELDS + EN_FIELDS
            is_defect_field = stripped.lower().startswith(DEFECT_FIELD_PREFIXES)

            # Font & indent
            if is_numbered_header:
                pdf.setFont("Helvetica-Bold", 10)
                x_pos = LEFT_MARGIN
            elif is_sub_item:
                pdf.setFont("Helvetica-Bold", 9)
                x_pos = LEFT_MARGIN + 20
            else:
                pdf.setFont("Helvetica", 9)
                if is_defect_field:
                    x_pos = LEFT_MARGIN + 40
                else:
                    x_pos = PARAGRAPH_INDENT

            prev_line_is_sub_item = is_sub_item

            # ============================================
            # WORD WRAP + JUSTIFY (ISI PERENGGAN SAHAJA)
            # ============================================
            words = stripped.split()
            current_line = ""

            for word in words:
                test_line = current_line + " " + word if current_line else word
                if pdf.stringWidth(test_line, "Helvetica", 9) <= TEXT_WIDTH:
                    current_line = test_line
                else:
                    if is_numbered_header:
                        # Header → kiri sahaja
                        pdf.drawString(x_pos, y, current_line)
                    else:
                        # ISI → JUSTIFY DI SINI
                        draw_justified_line(
                            pdf,
                            current_line,
                            x_pos,
                            y,
                            TEXT_WIDTH,
                            "Helvetica",
                            9
                        )

                    y -= LINE_HEIGHT
                    if y < 80:
                        draw_footer(pdf, width, labels)
                        pdf.showPage()
                        y = height - 50
                        pdf.setFont("Helvetica", 9)

                    current_line = word

            # Last line (JANGAN justify – standard dokumen rasmi)
            if current_line:
                pdf.drawString(x_pos, y, current_line)
                y -= LINE_HEIGHT

    # ============================================
    # APPENDIX: CLOSED CASE DETAILS (SAME FORMAT AS AI PREVIEW)
    # ============================================
    if role in ["Homeowner", "Developer", "Legal", "Admin"]:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50

        appendix_lines = build_closed_appendix_lines(closed_evidence_appendix, language)
        current_appendix_item = None
        for idx, raw_line in enumerate(appendix_lines):
            line = (raw_line or "").rstrip()

            if y < 80:
                draw_footer(pdf, width, labels)
                pdf.showPage()
                y = height - 50

            if not line:
                y -= 10
                continue

            is_header = bool(
                re.match(r"^[A-Z]\.\s+(Defect ID|Kecacatan ID)", line)
                or re.match(r"^\d+\.\s+(Defect ID|Kecacatan ID)", line)
                or line.startswith("APPENDIX A:")
                or line.startswith("LAMPIRAN A:")
            )

            header_match = re.match(r"^(?:[A-Z]|\d+)\.\s+(?:Defect ID|Kecacatan ID)\s+([^:]+):", line)
            if header_match:
                defect_id_text = header_match.group(1).strip()
                current_appendix_item = next(
                    (item for item in closed_evidence_appendix if str(item.get("id")) == defect_id_text),
                    None,
                )

                # Keep one full appendix item together when there is enough space on a fresh page.
                appendix_image_path = None
                if current_appendix_item:
                    appendix_image_path = _resolve_evidence_image_path(
                        evidence_dir,
                        current_appendix_item.get("id"),
                        current_appendix_item.get("filename"),
                    )

                block_end = len(appendix_lines)
                for j in range(idx + 1, len(appendix_lines)):
                    nxt = (appendix_lines[j] or "").strip()
                    if not nxt:
                        block_end = j + 1
                        break

                required_height = 0
                for j in range(idx, block_end):
                    candidate = (appendix_lines[j] or "").strip()
                    if not candidate:
                        required_height += 10
                    else:
                        wrapped_count = _estimate_wrapped_lines(candidate, width - 100)
                        required_height += wrapped_count * 14

                if appendix_image_path:
                    required_height += 110

                page_usable_height = (height - 50) - 80
                if required_height <= page_usable_height and y - required_height < 80:
                    draw_footer(pdf, width, labels)
                    pdf.showPage()
                    y = height - 50

            if is_header:
                font_name = "Helvetica-Bold"
                font_size = 10
            else:
                font_name = "Helvetica"
                font_size = 9

            x = 70 if line.startswith(":") else 50
            y = draw_wrapped_text(pdf, line, x, y, width - 100, font_name, font_size, 14)

            if line.startswith("Defect Image:") or line.startswith("Gambar Kecacatan:"):
                appendix_image_path = None
                if current_appendix_item:
                    appendix_image_path = _resolve_evidence_image_path(
                        evidence_dir,
                        current_appendix_item.get("id"),
                        current_appendix_item.get("filename"),
                    )

                if appendix_image_path:
                    if y < 170:
                        draw_footer(pdf, width, labels)
                        pdf.showPage()
                        y = height - 50
                    pdf.drawImage(ImageReader(appendix_image_path), 70, y - 95, width=180, height=95)
                    y -= 110

    # ============================================
    # SIGNATURE & METERAI (HALAMAN BERASINGAN)
    # ============================================
    # Start signature on a new page (BEST PRACTICE)
    draw_footer(pdf, width, labels)
    pdf.showPage()
    y = height - 50

    # Title
    pdf.setFont("Helvetica-Bold", 11)
    if language == "en":
        pdf.drawCentredString(width / 2, y, "Verification and Signature")
    else:
        pdf.drawCentredString(width / 2, y, "Pengesahan dan Tandatangan")
    
    y -= 90

    # Signature section
    pdf.setFont("Helvetica", 9)

    # Left: short line for date
    short_line = "." * 55
    # Right: long line for signature
    long_line = "." * 90

    # Calculate widths
    short_width = pdf.stringWidth(short_line, "Helvetica", 9)
    long_width = pdf.stringWidth(long_line, "Helvetica", 9)

    # Positions - left starts at 50, right ends at width-50
    left_x = 50
    right_x = width - 50 - long_width

    # Centers for labels
    left_center = left_x + (short_width / 2)
    right_center = right_x + (long_width / 2)

    # Row 1: Tarikh + Tandatangan
    pdf.drawString(left_x, y, short_line)
    pdf.drawString(right_x, y, long_line)
    y -= 20
    if language == "en":
        pdf.drawCentredString(left_center, y, "Date")
        pdf.drawCentredString(right_center, y, "Signature/Thumbprint of Claimant")
    else:
        pdf.drawCentredString(left_center, y, "Tarikh")
        pdf.drawCentredString(right_center, y, "Tandatangan/Cap ibu jari Pihak Yang Menuntut")

    # Row spacing (lebih luas)
    y -= 90

    # Row 2: Tarikh Pemfailan + Setiausaha
    pdf.drawString(left_x, y, short_line)
    pdf.drawString(right_x, y, long_line)
    y -= 20
    if language == "en":
        pdf.drawCentredString(left_center, y, "Filing Date")
        pdf.drawCentredString(right_center, y, "Secretary/Tribunal Officer")
    else:
        pdf.drawCentredString(left_center, y, "Tarikh Pemfailan")
        pdf.drawCentredString(right_center, y, "Setiausaha/Pegawai Tribunal")

    # Meterai
    y -= 100
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawCentredString(width / 2, y, "(SEAL)")
    else:
        pdf.drawCentredString(width / 2, y, "(METERAI)")

    # Filename based on role
    if role == "Legal":
        filename = labels["legal_filename"]
    elif role == "Developer":
        filename = labels["developer_filename"]
    else:
        filename = labels["homeowner_filename"]

    # Set PDF metadata so browser/PDF viewers display a proper document title.
    pdf.setTitle(os.path.splitext(filename)[0])
    pdf.setAuthor("Automated Compliance Report Generation")
    pdf.setSubject("Tribunal Compliance Report")

    # ==========================
    # DIGITAL VALIDATION HASH
    # ==========================
    report_string = json.dumps(report_data, sort_keys=True)
    digital_hash = hashlib.sha256(report_string.encode()).hexdigest()

    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(50, 30, f"Digital Validation Hash: {digital_hash}")

    draw_footer(pdf, width, labels)
    pdf.save()
    buffer.seek(0)

    # ==========================
    # AUDIT LOG: PDF EXPORTED
    # ==========================
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
    return render_template('role/dashboard/settings.html', user=current_user)

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
