# report_data.py
import os
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

def get_connection():
    from ..extensions import db
    return db.engine.raw_connection()

TRIBUNAL_NAME = "Tribunal Tuntutan Pengguna Malaysia"
DEFAULT_TRIBUNAL_LOCATION = "-"
DEFAULT_CLAIM_AMOUNT = "-"
DEFAULT_STATE_NAME = "-"
DEFAULT_ITEM_SERVICE = "Defect Repair During DLP"
IMPORTANT_NOTE = (
    "Laporan ini dijana oleh sistem sebagai dokumen sokongan kepada Borang 1 Tribunal Tuntutan Pengguna Malaysia (TTPM)."
)
DEFAULT_CLAIMANT_HOMEOWNER_USERNAME = os.getenv("DEFAULT_CLAIMANT_HOMEOWNER_USERNAME", "").strip()
DEFAULT_CLAIMANT_HOMEOWNER_ID = int(
    os.getenv("DEFAULT_CLAIMANT_HOMEOWNER_ID", os.getenv("SIMULATED_LOGIN_USER_ID", "1"))
)
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")


def _now_app_timezone():
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:
        if APP_TIMEZONE == "Asia/Kuala_Lumpur":
            return datetime.now(timezone.utc) + timedelta(hours=8)
        return datetime.now()

STATE_CODES = {
    "Selangor": "SGR",
    "Johor": "JHR",
    "Pulau Pinang": "PNG",
    "Perak": "PRK",
    "Kedah": "KDH",
    "Perlis": "PLS",
    "Negeri Sembilan": "NSN",
    "Melaka": "MLK",
    "Pahang": "PHG",
    "Terengganu": "TRG",
    "Kelantan": "KTN",
    "Sabah": "SBH",
    "Sarawak": "SWK",
    "Kuala Lumpur": "WPKL",
    "Putrajaya": "WPPJ",
    "Labuan": "WPLB",
}

ROLE_CONTEXTS = {
    "Homeowner": {
        "report_title": "Laporan Tuntutan Kecacatan Defect Liability Period (DLP)",
        "report_purpose": "Laporan ini disediakan bagi tujuan rujukan Tribunal.",
    },
    "Developer": {
        "report_title": "Laporan Pematuhan Pembaikan Defect Liability Period (DLP)",
        "report_purpose": "Laporan ini disediakan untuk menunjukkan status pembaikan dan pematuhan pemaju terhadap kecacatan yang dilaporkan.",
    },
    "Legal": {
        "report_title": "Laporan Gambaran Keseluruhan Pematuhan Defect Liability Period (DLP)",
        "report_purpose": "Laporan ini disediakan sebagai gambaran keseluruhan status kecacatan dan pematuhan untuk rujukan Tribunal.",
    },
}

def _ensure_report_metadata_tables():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS report_active_claimant")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS report_homeowner_profile (
                homeowner_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                ic_number VARCHAR(100),
                email VARCHAR(255),
                phone_number VARCHAR(100),
                address VARCHAR(255),
                court_location VARCHAR(255),
                state_name VARCHAR(100),
                claim_amount VARCHAR(100),
                item_service VARCHAR(255),
                transaction_date DATE,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS court_location VARCHAR(255)"
        )
        cur.execute(
            "ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS state_name VARCHAR(100)"
        )
        cur.execute(
            "ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS claim_amount VARCHAR(100)"
        )
        cur.execute(
            "ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS item_service VARCHAR(255)"
        )
        cur.execute(
            "ALTER TABLE report_homeowner_profile ADD COLUMN IF NOT EXISTS transaction_date DATE"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS report_respondent_profile (
                respondent_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                homeowner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                company_name VARCHAR(255) NOT NULL,
                registration_number VARCHAR(100),
                email VARCHAR(255),
                phone_number VARCHAR(100),
                address VARCHAR(255),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "ALTER TABLE report_respondent_profile ADD COLUMN IF NOT EXISTS homeowner_id INTEGER"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS report_claim_registry (
                claim_id VARCHAR(64) PRIMARY KEY,
                case_key VARCHAR(255) UNIQUE NOT NULL,
                case_number VARCHAR(6) NOT NULL,
                claim_year INTEGER NOT NULL,
                date_filed TIMESTAMP NOT NULL DEFAULT NOW(),
                state VARCHAR(100) NOT NULL,
                state_code VARCHAR(20) NOT NULL,
                homeowner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                respondent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "ALTER TABLE report_claim_registry ADD COLUMN IF NOT EXISTS state VARCHAR(100)"
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'report_claim_registry'
                      AND column_name = 'negeri'
                ) THEN
                    EXECUTE 'UPDATE report_claim_registry SET state = COALESCE(state, negeri)';
                END IF;
            END
            $$;
            """
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()


def _fetch_respondent_profile(cur, homeowner_id=None, respondent_user_id=None):
    if homeowner_id is not None:
        cur.execute(
            """
            SELECT respondent_id, homeowner_id, company_name, registration_number, email, phone_number, address
            FROM report_respondent_profile
            WHERE homeowner_id = %s
            ORDER BY updated_at DESC, respondent_id ASC
            LIMIT 1
            """,
            (homeowner_id,),
        )
        row = cur.fetchone()
        if row:
            return row

    if respondent_user_id is not None:
        cur.execute(
            """
            SELECT respondent_id, homeowner_id, company_name, registration_number, email, phone_number, address
            FROM report_respondent_profile
            WHERE respondent_id = %s
            LIMIT 1
            """,
            (respondent_user_id,),
        )
        row = cur.fetchone()
        if row:
            return row

    return None


def get_homeowner_claimants():
    _ensure_report_metadata_tables()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT homeowner_id, name, address, email
            FROM report_homeowner_profile
            ORDER BY homeowner_id ASC
            """
        )
        return [
            {
                "homeowner_id": row[0],
                "name": row[1] or "-",
                "unit": row[2] or "-",
                "email": row[3] or "-",
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def _is_missing_required(value):
    if value is None:
        return True
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned in {"", "-", "Unknown"}
    return False


def validate_report_requirements(role, user_id=None, claimant_user_id=None):
    # Normalize role string (e.g. 'homeowner' -> 'Homeowner')
    if role:
        role = role.strip().capitalize()
        if role == "Lawyer":
            role = "Legal"

    case_info, claimant, respondent, _, _, _ = _load_report_metadata(user_id=user_id, role=role, claimant_user_id=claimant_user_id)
    active_role = role or "Homeowner"

    required_case_fields = {
        "tribunal_location": "Homeowner profile (report_homeowner_profile): Court location",
        "state_name": "Homeowner profile (report_homeowner_profile): State",
        "claim_amount": "Homeowner profile (report_homeowner_profile): Claim amount",
        "transaction_date": "Homeowner profile (report_homeowner_profile): Transaction date",
    }
    required_claimant_fields = {
        "name": "Homeowner profile (report_homeowner_profile): Name",
        "national_id": "Homeowner profile (report_homeowner_profile): IC number",
        "address_line_1": "Homeowner profile (report_homeowner_profile): Address",
        "phone_number": "Homeowner profile (report_homeowner_profile): Phone number",
        "email": "Homeowner profile (report_homeowner_profile): Email",
    }
    required_respondent_fields = {
        "name": "Respondent profile (report_respondent_profile): Company name",
        "registration_no": "Respondent profile (report_respondent_profile): Registration number",
        "address_line_1": "Respondent profile (report_respondent_profile): Address",
        "phone_number": "Respondent profile (report_respondent_profile): Phone number",
        "email": "Respondent profile (report_respondent_profile): Email",
    }

    errors = []

    # Homeowner report requires complete claimant/case context.
    if active_role == "Homeowner":
        for key, label in required_case_fields.items():
            if _is_missing_required(case_info.get(key)):
                errors.append(f"Missing {label}")

    # Claimant (homeowner) identity is required for all report roles.
    if active_role in ("Homeowner", "Developer", "Legal", "Admin"):
        for key, label in required_claimant_fields.items():
            if _is_missing_required(claimant.get(key)):
                errors.append(f"Missing {label}")

    # Developer/Legal/Admin report requires respondent profile completeness.
    if active_role in ("Homeowner", "Developer", "Legal", "Admin"):
        for key, label in required_respondent_fields.items():
            if _is_missing_required(respondent.get(key)):
                errors.append(f"Missing {label}")

    return errors


def _load_report_metadata(user_id=None, role=None, claimant_user_id=None):
    _ensure_report_metadata_tables()

    conn = get_connection()
    cur = conn.cursor()
    try:
        case_info = {
            "tribunal_name": TRIBUNAL_NAME,
            "tribunal_location": DEFAULT_TRIBUNAL_LOCATION,
            "generated_date": _now_app_timezone().strftime("%d-%m-%Y"),
            "claim_amount": DEFAULT_CLAIM_AMOUNT,
            "item_service": DEFAULT_ITEM_SERVICE,
            "transaction_date": "-",
            "document_name": "Dokumen Sokongan Borang 1",
            "state_name": DEFAULT_STATE_NAME,
        }

        claimant = {
            "name": "-",
            "national_id": "-",
            "address_line_1": "-",
            "address_line_2": "-",
            "phone_number": "-",
            "email": "-",
            "description": "-",
        }

        respondent = {
            "name": "-",
            "registration_no": "-",
            "address_line_1": "-",
            "address_line_2": "-",
            "phone_number": "-",
            "email": "-",
            "description": "-",
        }

        user_row = None
        if user_id is not None:
            cur.execute(
                """
                SELECT id, full_name, unit, role, email, ic_number, phone_number
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            user_row = cur.fetchone()

        if user_row:
            _, full_name, unit, user_role, user_email, user_ic_number, user_phone_number = user_row
            active_role = (role or user_role or "Homeowner").strip().capitalize()
            if active_role == "Lawyer":
                active_role = "Legal"

            if active_role == "Homeowner":
                homeowner_row = None
                cur.execute(
                    """
                    SELECT name, ic_number, email, phone_number, address,
                           court_location, state_name, claim_amount, item_service, transaction_date
                    FROM report_homeowner_profile
                    WHERE homeowner_id = %s
                    """,
                    (user_id,),
                )
                homeowner_row = cur.fetchone()
                if homeowner_row:
                    claimant = {
                        "name": homeowner_row[0] or claimant["name"],
                        "national_id": homeowner_row[1] or claimant["national_id"],
                        "email": homeowner_row[2] or claimant["email"],
                        "phone_number": homeowner_row[3] or claimant["phone_number"],
                        "address_line_1": homeowner_row[4] or claimant["address_line_1"],
                        "address_line_2": "",
                        "description": "Pemilik unit kediaman",
                    }
                    case_info["tribunal_location"] = homeowner_row[5] or case_info["tribunal_location"]
                    case_info["state_name"] = homeowner_row[6] or case_info["state_name"]
                    case_info["claim_amount"] = homeowner_row[7] or case_info["claim_amount"]
                    case_info["item_service"] = homeowner_row[8] or case_info["item_service"]
                    if homeowner_row[9]:
                        case_info["transaction_date"] = homeowner_row[9].strftime("%d-%m-%Y")
                # Only fallback to user table defaults if the profile value is truly missing/placeholder
                if _is_missing_required(claimant.get("name")):
                    claimant["name"] = full_name or claimant["name"]
                if _is_missing_required(claimant.get("national_id")):
                    claimant["national_id"] = user_ic_number or claimant["national_id"]
                if _is_missing_required(claimant.get("email")):
                    claimant["email"] = user_email or claimant["email"]
                if _is_missing_required(claimant.get("phone_number")):
                    claimant["phone_number"] = user_phone_number or claimant["phone_number"]
                
                # IMPORTANT: If address is already set from profile (homeowner_row[4]), 
                # do not override it with unit unless it is empty or '-'
                if not claimant.get("address_line_1") or claimant.get("address_line_1") == "-":
                    if unit and unit != "None":
                        claimant["address_line_1"] = unit or claimant["address_line_1"]

                respondent_row = _fetch_respondent_profile(cur, homeowner_id=user_id)
                if respondent_row:
                    respondent = {
                        "name": respondent_row[2] or respondent["name"],
                        "registration_no": respondent_row[3] or respondent["registration_no"],
                        "email": respondent_row[4] or respondent["email"],
                        "phone_number": respondent_row[5] or respondent["phone_number"],
                        "address_line_1": respondent_row[6] or respondent["address_line_1"],
                        "address_line_2": "",
                        "description": "Pemaju projek perumahan",
                    }
            elif active_role in ("Developer", "Legal", "Admin"):
                claimant_row = None

                target_homeowner_id = claimant_user_id or DEFAULT_CLAIMANT_HOMEOWNER_ID
                if target_homeowner_id:
                    cur.execute(
                        """
                        SELECT name, ic_number, email, phone_number, address,
                               court_location, state_name, claim_amount, item_service, transaction_date
                        FROM report_homeowner_profile
                        WHERE homeowner_id = %s
                        LIMIT 1
                        """,
                        (target_homeowner_id,),
                    )
                    claimant_row = cur.fetchone()

                if not claimant_row:
                    # Fallback only if configured homeowner profile is unavailable.
                    cur.execute(
                        """
                        SELECT name, ic_number, email, phone_number, address,
                               court_location, state_name, claim_amount, item_service, transaction_date
                        FROM report_homeowner_profile
                        ORDER BY homeowner_id ASC
                        LIMIT 1
                        """
                    )
                    claimant_row = cur.fetchone()
                if claimant_row:
                    claimant = {
                        "name": claimant_row[0] or claimant["name"],
                        "national_id": claimant_row[1] or claimant["national_id"],
                        "email": claimant_row[2] or claimant["email"],
                        "phone_number": claimant_row[3] or claimant["phone_number"],
                        "address_line_1": claimant_row[4] or claimant["address_line_1"],
                        "address_line_2": "",
                        "description": "Pemilik unit kediaman",
                    }
                    case_info["tribunal_location"] = claimant_row[5] or case_info["tribunal_location"]
                    case_info["state_name"] = claimant_row[6] or case_info["state_name"]
                    case_info["claim_amount"] = claimant_row[7] or case_info["claim_amount"]
                    case_info["item_service"] = claimant_row[8] or case_info["item_service"]
                    if claimant_row[9]:
                        case_info["transaction_date"] = claimant_row[9].strftime("%d-%m-%Y")

                respondent_row = _fetch_respondent_profile(cur, respondent_user_id=user_id)
                if respondent_row:
                    respondent = {
                        "name": respondent_row[2] or respondent["name"],
                        "registration_no": respondent_row[3] or respondent["registration_no"],
                        "email": respondent_row[4] or respondent["email"],
                        "phone_number": respondent_row[5] or respondent["phone_number"],
                        "address_line_1": respondent_row[6] or respondent["address_line_1"],
                        "address_line_2": "",
                        "description": "Pemaju projek perumahan",
                    }
                if _is_missing_required(respondent.get("name")):
                    respondent["name"] = full_name or respondent["name"]
                if _is_missing_required(respondent.get("email")):
                    respondent["email"] = user_email or respondent["email"]
                if _is_missing_required(respondent.get("phone_number")):
                    respondent["phone_number"] = user_phone_number or respondent["phone_number"]
                if _is_missing_required(respondent.get("address_line_1")):
                    respondent["address_line_1"] = unit or respondent["address_line_1"]

        negeri_codes = dict(STATE_CODES)
        role_contexts = dict(ROLE_CONTEXTS)
        nota_penting = IMPORTANT_NOTE

        return case_info, claimant, respondent, negeri_codes, role_contexts, nota_penting
    finally:
        cur.close()
        conn.close()


# ==================================================
# BUILD SUMMARY STATISTICS (FROM DASHBOARD STATS)
# ==================================================

def build_summary_stats(stats, defects=None):
    """
    Build structured statistical summary
    Includes overdue count and HDA non-compliance count
    """

    overdue_count = 0
    hda_non_compliant_count = 0

    if defects:
        overdue_count = len([d for d in defects if d.get("is_overdue")])
        hda_non_compliant_count = len([d for d in defects if d.get("hda_compliant") is False])

    return {
        "total_defects": stats.get("total", 0),
        "pending_defects": stats.get("pending", 0),
        "investigation_defects": stats.get("investigation", 0),
        "completed_defects": stats.get("completed", 0),
        "critical_defects": stats.get("critical", 0),
        "overdue_defects": overdue_count,
        "hda_non_compliant_defects": hda_non_compliant_count
    }

# ==================================================
# BUILD DEFECT DETAILS (TABLE → REPORT)
# ==================================================

def build_defect_list(defects, role):
    """
    Convert raw defect data into structured report format.
    Remarks are included ONLY for Homeowner.
    """

    report_defects = []

    for d in defects:
        days_to_complete = "-"
        if d.get("reported_date") and d.get("completed_date"):
            try:
                reported_date_obj = datetime.strptime(str(d.get("reported_date"))[:10], "%Y-%m-%d").date()
                completed_date_obj = datetime.strptime(str(d.get("completed_date"))[:10], "%Y-%m-%d").date()
                days_to_complete = max((completed_date_obj - reported_date_obj).days, 0)
            except Exception:
                days_to_complete = "-"

        evidence_filename = d.get("evidence_filename")
        defect_item = {
            "defect_id": d.get("id"),
            "unit": d.get("unit", "-"),
            "description": d.get("desc", "-"),
            "status": d.get("status", "-"),
            "reported_date": d.get("reported_date", "-"),
            "deadline": d.get("deadline", "-"),
            "actual_completion_date": d.get("completed_date") if d.get("completed_date") else "-",
            "days_to_complete": days_to_complete,
            "overdue": "Yes" if d.get("is_overdue") else "No",
            "hda_compliance_30_days": "Yes" if d.get("hda_compliant") else "No",
            "priority": d.get("urgency", "Normal"),
            "evidence_image": f"evidence/{evidence_filename}" if evidence_filename else "-"
        }

        # Only Homeowner sees remarks
        if role == "Homeowner" and d.get("remarks"):
            defect_item["remarks"] = d.get("remarks")

        report_defects.append(defect_item)

    return report_defects

# ==================================================
# GENERATE CLAIM NUMBER (NO TUNTUTAN)
# Format: TTPM/SGR/2026/000001
# ==================================================

def generate_no_tuntutan(negeri, running_no, negeri_codes):
    tahun = _now_app_timezone().year

    negeri_code = negeri_codes.get(negeri, "UNK")
    # UNK = Unknown (safety fallback)

    return f"TTPM/{negeri_code}/{tahun}/{running_no:06d}"


def get_or_create_claim_number(state_name, negeri_codes, case_key, homeowner_id=None, respondent_id=None):
    _ensure_report_metadata_tables()

    conn = get_connection()
    cur = conn.cursor()
    try:
        claim_year = _now_app_timezone().year
        state_code = negeri_codes.get(state_name, "UNK")

        resolved_homeowner_id = homeowner_id
        if resolved_homeowner_id is None:
            cur.execute(
                """
                SELECT homeowner_id
                FROM report_homeowner_profile
                ORDER BY updated_at DESC, homeowner_id ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                resolved_homeowner_id = row[0]

        if resolved_homeowner_id is None:
            cur.execute(
                """
                SELECT id
                FROM users
                WHERE role = 'Homeowner'
                ORDER BY id ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                resolved_homeowner_id = row[0]

        if resolved_homeowner_id is None:
            raise ValueError("Cannot generate claim number because no homeowner profile exists.")

        # Always issue a new serial for each generation/export request.
        unique_case_key = f"{case_key}:{uuid.uuid4().hex}"

        cur.execute(
            "SELECT COALESCE(MAX(CAST(case_number AS INTEGER)), 0) + 1 FROM report_claim_registry WHERE claim_year = %s AND state_code = %s",
            (claim_year, state_code),
        )
        running_no = int(cur.fetchone()[0])
        case_number = f"{running_no:06d}"
        claim_id = f"TTPM/{state_code}/{claim_year}/{case_number}"

        cur.execute(
            """
            INSERT INTO report_claim_registry (
                claim_id, case_key, case_number, claim_year, date_filed, state, state_code, homeowner_id, respondent_id
            )
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s)
            RETURNING claim_id
            """,
            (claim_id, unique_case_key, case_number, claim_year, state_name, state_code, resolved_homeowner_id, respondent_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        cur.close()
        conn.close()

# ==================================================
# ROLE CONTEXT (AI GUIDANCE STRUCTURE)
# ==================================================

def build_role_context(role, role_contexts):
    if role in role_contexts:
        return role_contexts[role]
    if "Legal" in role_contexts:
        return role_contexts["Legal"]
    return {"report_title": "Report", "report_purpose": ""}


# ==================================================
# FINAL REPORT DATA (SEND THIS TO AI)
# ==================================================

def build_report_data(
    role,
    defects,
    stats,
    running_no=None,
    user_id=None,
    case_key=None,
    claimant_user_id=None,
    forced_claim_number=None,
    project_filter=None,
):
    # Normalize role string (e.g. 'homeowner' -> 'Homeowner')
    if role:
        role = role.strip().capitalize()
        if role == "Lawyer":
            role = "Legal"

    (
        case_info,
        claimant,
        respondent,
        negeri_codes,
        role_contexts,
        nota_penting,
    ) = _load_report_metadata(user_id=user_id, role=role, claimant_user_id=claimant_user_id)
    state_name = case_info["state_name"]

    if forced_claim_number:
        claim_number = str(forced_claim_number)
    elif case_key:
        resolved_homeowner_id = user_id if role == "Homeowner" else claimant_user_id or user_id
        claim_number = get_or_create_claim_number(
            state_name,
            negeri_codes,
            case_key,
            homeowner_id=resolved_homeowner_id,
            respondent_id=user_id if role in ("Developer", "Legal", "Admin") else None,
        )
    else:
        if running_no is None:
            running_no = 1
        claim_number = generate_no_tuntutan(state_name, running_no, negeri_codes)

    case_info = case_info.copy()
    case_info["claim_id"] = claim_number
    case_info["claim_number"] = claim_number
    case_info["state_code"] = negeri_codes.get(state_name, "UNK")
    selected_project_name = str(project_filter or "").strip()
    if not selected_project_name:
        if defects:
            selected_project_name = (
                defects[0].get("project_name")
                or defects[0].get("scan_name")
                or defects[0].get("unit")
                or "-"
            )
        else:
            selected_project_name = "-"
    case_info["project_name"] = selected_project_name

    return {
        "case_info": case_info,
        "claimant": claimant,
        "respondent": respondent,
        "role_context": build_role_context(role, role_contexts),
        "summary_stats": build_summary_stats(stats, defects),
        "defect_list": build_defect_list(defects, role),
        "important_note": nota_penting,
    }
