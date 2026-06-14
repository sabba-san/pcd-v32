"""
PDF generation service for Tribunal claim forms (Borang 1 TTPM).
Extracted from module3/routes.py to reduce controller bloat.
"""
import os
import re
import json
import hashlib
import base64
import uuid
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ---- Image Helpers ----

VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.gif', '.bmp', '.webp'}


def _is_valid_image_path(path):
    """Return True only if the path has a recognised image extension."""
    if not path:
        return False
    ext = os.path.splitext(str(path))[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS


def _resolve_evidence_image_path(evidence_dir, defect_id, evidence_filename=None):
    """Resolve an absolute path to an evidence image."""
    if not evidence_dir or not os.path.isdir(evidence_dir):
        return None

    candidate_name = (evidence_filename or "").strip()

    # 1) Try exact filename from metadata
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

    # 2) Legacy defect_<id>.ext naming
    if candidate_name and candidate_name not in ("-", "gambar", "image") and _is_valid_image_path(candidate_name):
        prefix = f"defect_{defect_id}.".lower()
        for fname in os.listdir(evidence_dir):
            if fname.lower().startswith(prefix) and _is_valid_image_path(fname):
                full_path = os.path.join(evidence_dir, fname)
                if os.path.isfile(full_path):
                    return full_path

    return None


def _get_evidence_image_bytesio(defect_id):
    """Retrieve evidence image from database as BytesIO (Base64 fallback)."""
    try:
        from app.models import Evidence
        evidence = Evidence.query.filter_by(defect_id=defect_id).first()
        if evidence and evidence.image_data:
            return BytesIO(base64.b64decode(evidence.image_data))
    except Exception:
        pass
    return None


# ---- PDF Drawing Helpers ----

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
    paragraphs = text.split('\n')
    for para in paragraphs:
        if not para.strip():
            y -= leading
            continue
        words = para.split()
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
    
    return min(y_label, y_val)


# ---- Calculation Helpers ----

def calculate_days_to_complete(reported_date, completed_date):
    if not reported_date or not completed_date:
        return None

    try:
        reported_date_obj = datetime.strptime(str(reported_date)[:10], "%Y-%m-%d").date()
        completed_date_obj = datetime.strptime(str(completed_date)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

    return max((completed_date_obj - reported_date_obj).days, 0)


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


# ---- Encryption Helpers (Base64) ----

def encrypt_text(text):
    if not text:
        return ""
    return base64.b64encode(text.encode()).decode()


def decrypt_text(text):
    if not text:
        return ""
    return base64.b64decode(text.encode()).decode()


# ---- Estimate Helpers ----

def _estimate_wrapped_lines_with_font(pdf, text, font_name, font_size, max_width):
    words = text.split()
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


def _estimate_wrapped_lines_with_breaks(pdf, text, font_name, font_size, max_width):
    paragraphs = text.split('\n')
    total_lines = 0
    for para in paragraphs:
        if not para.strip():
            total_lines += 1
            continue
        words = para.split()
        if not words:
            total_lines += 1
            continue
        line = ""
        for word in words:
            candidate = f"{line} {word}" if line else word
            if pdf.stringWidth(candidate, font_name, font_size) <= max_width:
                line = candidate
            else:
                total_lines += 1
                line = word
        if line:
            total_lines += 1
    return max(total_lines, 1)


def _estimate_wrapped_lines(text, max_width):
    """Estimate how many lines text will wrap to (approximate)."""
    words = text.split()
    if not words:
        return 1

    count = 0
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        # Approximate: average char width ~5px for Helvetica 9
        if len(test_line) * 5 <= max_width:
            current_line = test_line
        else:
            count += 1
            current_line = word
    if current_line:
        count += 1
    return max(count, 1)


# ---- Appendix Helper ----

def build_closed_appendix_lines(closed_evidence_appendix, language, auto_close_days=14):
    """Build a consistent closed-case appendix text block."""
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
            "Tiada rekod kes ditutup buat masa ini." if language == "ms"
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
            appendix_lines.append(f"Peraturan Ditutup: Ditutup selepas {auto_close_days} hari dari tarikh siap")
            appendix_lines.append(f"Muat Naik: {format_pdf_date(item.get('uploaded_at'))}")
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
            appendix_lines.append(f"Closed Rule: Closed after {auto_close_days} days from completion")
            appendix_lines.append(f"Uploaded: {format_pdf_date(item.get('uploaded_at'))}")
            _fn_en = (item.get('filename') or '').strip()
            if _fn_en and _fn_en not in ('-', 'gambar', 'image') and _is_valid_image_path(_fn_en):
                appendix_lines.append("Defect Image: [image]")
            else:
                appendix_lines.append("Defect Image: No evidence image uploaded.")

        appendix_lines.append("")

    return appendix_lines


# ---- Defect Card Drawer (Side-by-Side Layout) ----

def draw_defect_card(pdf, defect, y, width, language, labels, role, evidence_dir, card_index, height, extra_fields=None):
    """
    Draw a single defect as a side-by-side card with text left, image right.
    extra_fields: optional list of (label, value) tuples appended after standard fields.
    Returns (new_y, did_page_break).
    """
    CARD_MARGIN = 45
    CARD_WIDTH = width - 2 * CARD_MARGIN
    TEXT_X = CARD_MARGIN + 10
    TEXT_COL_WIDTH = int(CARD_WIDTH * 0.62)
    VALUE_X = TEXT_X + 110
    VALUE_WIDTH = TEXT_COL_WIDTH - 120
    DIVIDER_X = TEXT_X + TEXT_COL_WIDTH

    # --- Resolve evidence image (preserves all existing fallback logic) ---
    image_path = _resolve_evidence_image_path(
        evidence_dir, defect.get("id"), defect.get("evidence_filename")
    )
    if not image_path and defect.get("evidence_file_path"):
        raw_fp = defect.get("evidence_file_path", "").strip()
        if raw_fp and _is_valid_image_path(raw_fp):
            static_candidate = os.path.join(evidence_dir, os.path.basename(raw_fp))
            if os.path.exists(static_candidate):
                image_path = static_candidate
    if not image_path and defect.get("image_path"):
        candidate_path = os.path.join(evidence_dir, os.path.basename(defect.get("image_path", "")))
        if os.path.exists(candidate_path):
            image_path = candidate_path

    img_to_draw = None
    if image_path and os.path.exists(image_path):
        img_to_draw = image_path
    else:
        img_to_draw = _get_evidence_image_bytesio(defect.get("id"))

    has_image = img_to_draw is not None

    # --- Pre-compute long text values for height estimation and drawing ---
    desc = defect.get("desc", "-")
    if defect.get("hda_compliant"):
        hda_msg = (
            "Rectified within thirty (30) days from date of notification pursuant to HDA"
            if language == "en"
            else "Diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"
        )
    else:
        hda_msg = (
            "Failed to Comply with 30-Day Requirement under HDA"
            if language == "en"
            else "Tidak diselesaikan dalam tempoh tiga puluh (30) hari dari tarikh notifikasi menurut HDA"
        )

    # --- Estimate card height ---
    desc_lines = _estimate_wrapped_lines_with_font(pdf, desc, "Helvetica", 9, VALUE_WIDTH)
    hda_lines = _estimate_wrapped_lines_with_font(
        pdf, f": {hda_msg}", "Helvetica", 9, VALUE_WIDTH
    )

    text_px = 18  # header (bold, larger)
    text_px += desc_lines * 13  # description (wrapped)
    text_px += 7 * 13  # 7 single-line fields: Unit, Status, Reported, Deadline, Completed, Days, Overdue
    text_px += hda_lines * 13  # HDA compliance (wrapped)
    if defect.get("priority"):
        text_px += 13
    if role.lower() == "homeowner" and defect.get("remarks"):
        # Count each non-empty bullet line; +8 for top separator gap
        raw_bullets = [ln for ln in defect.get("remarks", "").split("\n") if ln.strip()]
        rem_lines = sum(
            _estimate_wrapped_lines_with_font(pdf, ln.strip(), "Helvetica", 9, VALUE_WIDTH)
            for ln in raw_bullets
        ) or 1
        text_px += 8 + 13 + rem_lines * 15 + max(len(raw_bullets) - 1, 0) * 4
    if extra_fields:
        for _label, _value in extra_fields:
            v_lines = _estimate_wrapped_lines_with_font(
                pdf, str(_value), "Helvetica", 9, VALUE_WIDTH
            )
            text_px += 13 + v_lines * 13  # 1 line for label + wrapped value lines

    CARD_PAD = 12
    text_block_height = text_px + CARD_PAD * 2
    MIN_CARD_HEIGHT = 260 if has_image else 120
    card_height = max(text_block_height, MIN_CARD_HEIGHT)
    card_height += 6  # bottom gap after border

    # --- Page break check (guarantees entire card fits on one page) ---
    did_page_break = False
    if y - card_height < 60:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50
        did_page_break = True

    # --- Draw card border (light fill + rounded rect) ---
    pdf.setFillColorRGB(0.98, 0.98, 0.98)
    pdf.setStrokeColorRGB(0.61, 0.64, 0.69)
    pdf.roundRect(CARD_MARGIN, y - card_height, CARD_WIDTH, card_height, 4, fill=1, stroke=1)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setStrokeColorRGB(0, 0, 0)

    # --- Draw vertical divider if image exists ---
    if has_image:
        pdf.setStrokeColorRGB(0.8, 0.8, 0.8)
        pdf.line(DIVIDER_X, y - 8, DIVIDER_X, y - card_height + 8)
        pdf.setStrokeColorRGB(0, 0, 0)

    # ================================================================
    # Draw text fields (left column)
    # ================================================================
    cy = y - 14

    # Defect header
    pdf.setFont("Helvetica-Bold", 10)
    letter = chr(64 + card_index) if card_index <= 26 else chr(64 + (card_index % 26))
    header_text = f"{letter}. {labels.get('defect_id', 'Defect ID')} {defect.get('id', '')}:"
    pdf.drawString(TEXT_X, cy, header_text)
    cy -= 16
    pdf.setFont("Helvetica", 9)

    # Description
    pdf.drawString(TEXT_X, cy, labels.get("description", "Description"))
    cy = draw_wrapped_text(pdf, f": {desc}", VALUE_X, cy, VALUE_WIDTH)

    # Unit
    pdf.drawString(TEXT_X, cy, labels.get("unit", "Unit"))
    pdf.drawString(VALUE_X, cy, f": {defect.get('unit', '-')}")
    cy -= 13

    # Status
    pdf.drawString(TEXT_X, cy, labels.get("status", "Status"))
    pdf.drawString(VALUE_X, cy, f": {defect.get('status', '-')}")
    cy -= 13

    # Reported Date
    pdf.drawString(TEXT_X, cy, labels.get("reported_date", "Reported Date"))
    clean_reported = format_pdf_date(defect.get("reported_date"))
    pdf.drawString(VALUE_X, cy, f": {clean_reported}")
    cy -= 13

    # Scheduled Completion Date
    pdf.drawString(TEXT_X, cy, labels.get("deadline", "Scheduled Completion Date"))
    pdf.drawString(VALUE_X, cy, f": {defect.get('deadline', '-')}")
    cy -= 13

    # Actual Completion Date
    pdf.drawString(TEXT_X, cy, labels.get("actual_completion_date", "Actual Completion Date"))
    completed_val = defect.get("completed_date") if defect.get("completed_date") else "-"
    pdf.drawString(VALUE_X, cy, f": {completed_val}")
    cy -= 13

    # Days to Complete
    days_to_complete = calculate_days_to_complete(
        defect.get("reported_date"), defect.get("completed_date")
    )
    days_str = str(days_to_complete) if days_to_complete is not None else "-"
    if language == "en":
        pdf.drawString(TEXT_X, cy, "Days to Complete")
        pdf.drawString(VALUE_X, cy, f": {days_str}")
    else:
        pdf.drawString(TEXT_X, cy, "Tempoh Siap (Hari)")
        pdf.drawString(VALUE_X, cy, f": {days_str}")
    cy -= 13

    # HDA Compliance
    hda_label = "HDA Compliance (30 Days)" if language == "en" else "Pematuhan HDA (30 Hari)"
    pdf.drawString(TEXT_X, cy, hda_label)
    cy = draw_wrapped_text(pdf, f": {hda_msg}", VALUE_X, cy, VALUE_WIDTH)

    # Overdue
    is_overdue = defect.get("is_overdue", False)
    overdue_str = "Yes" if language == "en" else "Ya" if is_overdue else ("No" if language == "en" else "Tidak")
    pdf.drawString(TEXT_X, cy, "Overdue" if language == "en" else "Melebihi Tarikh")
    pdf.drawString(VALUE_X, cy, f": {overdue_str}")
    cy -= 13

    # Priority
    if defect.get("priority"):
        pdf.drawString(TEXT_X, cy, labels.get("priority", "Priority"))
        pdf.drawString(VALUE_X, cy, f": {defect['priority']}")
        cy -= 13

    # Remarks (homeowner only) — rendered as spaced bullet list
    if role.lower() == "homeowner" and defect.get("remarks"):
        # Thin separator above remarks block
        cy -= 6
        pdf.setStrokeColorRGB(0.78, 0.78, 0.78)
        pdf.line(TEXT_X, cy, DIVIDER_X - 6, cy)
        pdf.setStrokeColorRGB(0, 0, 0)
        cy -= 8

        # "Ulasan" / "Remarks" label — on its own line
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(TEXT_X, cy, labels.get("remarks", "Ulasan" if language != "en" else "Remarks"))
        cy -= 14  # drop a full line so bullets start BELOW the label
        pdf.setFont("Helvetica", 9)

        # Render each bullet on its own line with a small gap between
        raw_remarks = defect.get("remarks", "")
        bullets = [ln.strip() for ln in raw_remarks.split("\n") if ln.strip()]
        BULLET_INDENT = TEXT_X + 10  # slight indent under the label
        for bullet in bullets:
            cy = draw_wrapped_text(
                pdf, bullet, BULLET_INDENT, cy, VALUE_WIDTH + (VALUE_X - BULLET_INDENT),
                "Helvetica", 9, 14
            )
            cy -= 4  # small gap between bullets

    # Extra fields (appendix-specific)
    if extra_fields:
        for f_label, f_value in extra_fields:
            pdf.drawString(TEXT_X, cy, f_label)
            cy = draw_wrapped_text(pdf, f": {f_value}", VALUE_X, cy, VALUE_WIDTH)

    # ================================================================
    # Draw evidence image (right column, vertically centered)
    # ================================================================
    if has_image:
        IMG_COL_X = DIVIDER_X + 8
        IMG_COL_W = CARD_WIDTH - (IMG_COL_X - CARD_MARGIN) - 10
        img_h = min(240, card_height - 20)
        img_y = y - (card_height / 2) - (img_h / 2)
        try:
            pdf.drawImage(
                ImageReader(img_to_draw),
                IMG_COL_X, img_y,
                width=IMG_COL_W, height=img_h,
                preserveAspectRatio=True
            )
        except Exception:
            pdf.setFont("Helvetica-Oblique", 8)
            fallback_msg = "Error: Evidence image not found." if language == "en" else "Ralat: Imej bukti tidak ditemui."
            pdf.drawString(IMG_COL_X, y - card_height / 2, fallback_msg)

    return y - card_height - 6, did_page_break


# ---- Timezone / Certificate Helpers ----

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")


def _now_app_timezone():
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE))
    except Exception:
        if APP_TIMEZONE == "Asia/Kuala_Lumpur":
            return datetime.now(timezone.utc) + timedelta(hours=8)
        return datetime.now()


def _format_datetime_certificate(dt, language):
    if language == "ms":
        bulan_bm = {
            1: "Januari", 2: "Februari", 3: "Mac", 4: "April",
            5: "Mei", 6: "Jun", 7: "Julai", 8: "Ogos",
            9: "September", 10: "Oktober", 11: "November", 12: "Disember",
        }
        return f"{dt.day:02d} {bulan_bm[dt.month]} {dt.year}, {dt.strftime('%H:%M')}"
    return dt.strftime("%d %B %Y, %H:%M")


def render_certificate_page(pdf, width, height, report_data, labels, language, digital_hash):
    """
    Draw the Certificate of Defect Record Compliance Summary page.
    Must be called after pdf.showPage() so it starts on a fresh page.
    """
    pdf.showPage()

    LEFT_MARGIN = 50
    RIGHT_MARGIN = width - 50
    CONTENT_WIDTH = width - 100
    BOX_X = LEFT_MARGIN
    BOX_WIDTH = CONTENT_WIDTH
    LABEL_COLON = 200
    VALUE_X = 210
    VALUE_WIDTH = RIGHT_MARGIN - VALUE_X
    SECTION_GAP = 28
    BOX_PADDING = 8

    y = 800

    # ── Title ──
    pdf.setFont("Helvetica-Bold", 14)
    if language == "en":
        pdf.drawCentredString(width / 2, y, "Certificate of Defect Record Compliance Summary")
    else:
        pdf.drawCentredString(width / 2, y, "Sijil Ringkasan Pematuhan Rekod Kecacatan")
    y -= 24

    # Subtitle line
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(width / 2, y, "-" * 90)
    y -= 18

    case_info = report_data.get("case_info", {})
    summary_stats = report_data.get("summary_stats", {})
    now = _now_app_timezone()
    formatted_dt = _format_datetime_certificate(now, language)
    claim_number = case_info.get("claim_number", "-")
    generated_date = case_info.get("generated_date", formatted_dt)

    total = int(summary_stats.get("total_defects", 0))
    completed = int(summary_stats.get("completed_defects", 0))
    pending = int(summary_stats.get("pending_defects", 0))
    investigation = int(summary_stats.get("investigation_defects", 0))
    not_completed = pending + investigation
    rate = (completed / total * 100) if total > 0 else 0.0

    if language == "en":
        if total > 0 and completed >= total:
            status_text = "Complete"
        elif completed > 0:
            status_text = "In Review"
        else:
            status_text = "In Progress"
    else:
        if total > 0 and completed >= total:
            status_text = "Lengkap"
        elif completed > 0:
            status_text = "Dalam Semakan"
        else:
            status_text = "Dalam Proses"

    signature_id = hashlib.sha256(
        (digital_hash + str(uuid.uuid4())).encode()
    ).hexdigest()[:16]

    # ── Helper to draw a boxed section ──
    def _draw_section(title, pairs, start_y):
        """pairs: list of (label, value) tuples. Draws box, returns new y."""
        row_height = 16
        header_height = 20
        box_pad = 10
        n_rows = max(len(pairs), 1)
        box_h = header_height + n_rows * row_height + box_pad * 2

        if start_y - box_h < 60:
            return start_y

        y0 = start_y
        # Section title inside box
        pdf.setFont("Helvetica-Bold", 10)
        if language == "en":
            pdf.drawString(BOX_X + box_pad, y0 - 14, title)
        else:
            pdf.drawString(BOX_X + box_pad, y0 - 14, title)

        # Box around entire section
        pdf.rect(BOX_X, y0 - box_h, BOX_WIDTH, box_h)

        # Draw rows
        pdf.setFont("Helvetica", 9)
        ry = y0 - header_height - box_pad
        for label, value in pairs:
            pdf.drawString(BOX_X + box_pad, ry, str(label))
            pdf.drawString(BOX_X + LABEL_COLON, ry, ":")
            # Wrap value text if needed
            val_str = str(value)
            vw = pdf.stringWidth(val_str, "Helvetica", 9)
            if vw <= BOX_WIDTH - LABEL_COLON - box_pad * 2 - 10:
                pdf.drawString(BOX_X + LABEL_COLON + 10, ry, val_str)
            else:
                ry = draw_wrapped_text(
                    pdf, val_str, BOX_X + LABEL_COLON + 10, ry,
                    BOX_WIDTH - LABEL_COLON - box_pad * 2 - 15,
                    "Helvetica", 9, 14
                )
                continue
            ry -= row_height

        return y0 - box_h - SECTION_GAP

    # ── 1. Maklumat Laporan / Report Information ──
    if language == "en":
        section1_title = "Report Information"
    else:
        section1_title = "Maklumat Laporan"

    y = _draw_section(section1_title, [
        ("ID Laporan" if language == "ms" else "Report ID", claim_number),
        ("ID Tandatangan" if language == "ms" else "Signature ID", signature_id),
        ("Tarikh & Masa" if language == "ms" else "Date & Time", formatted_dt),
    ], y)

    # ── 2. Status Pematuhan / Compliance Status ──
    if language == "en":
        section2_title = "Compliance Status"
        status_label = "Status"
    else:
        section2_title = "Status Pematuhan"
        status_label = "Status"

    y = _draw_section(section2_title, [
        (status_label, status_text),
    ], y)

    # ── 3. Ringkasan Kecacatan / Defect Summary ──
    if language == "en":
        section3_title = "Defect Summary"
        label_total = "Total Defects"
        label_completed = "Completed Defects"
        label_rate = "Resolution Rate"
    else:
        section3_title = "Ringkasan Kecacatan"
        label_total = "Jumlah Kecacatan"
        label_completed = "Bilangan Kecacatan Diselesaikan"
        label_rate = "Kadar Penyelesaian"

    y = _draw_section(section3_title, [
        (label_total, str(total)),
        (label_completed, str(completed)),
        (label_rate, f"{rate:.1f}%"),
    ], y)

    # ── 4. Integriti Data / Data Integrity ──
    if language == "en":
        section4_title = "Data Integrity"
        hash_label = "SHA-256 Hash"
    else:
        section4_title = "Integriti Data"
        hash_label = "SHA-256"

    display_hash = digital_hash[:45] + "..."

    # Draw hash in a smaller font with wrapping
    hash_box_h = 70
    if y - hash_box_h < 60:
        return y

    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(BOX_X + BOX_PADDING, y - 14, section4_title)
    else:
        pdf.drawString(BOX_X + BOX_PADDING, y - 14, section4_title)
    pdf.rect(BOX_X, y - hash_box_h, BOX_WIDTH, hash_box_h)

    pdf.setFont("Courier", 8)
    yh = y - 30
    pdf.drawString(BOX_X + BOX_PADDING, yh, hash_label)
    pdf.drawString(BOX_X + LABEL_COLON, yh, ":")
    yh = draw_wrapped_text(
        pdf, display_hash, BOX_X + LABEL_COLON + 10, yh,
        BOX_WIDTH - LABEL_COLON - BOX_PADDING * 2 - 15,
        "Courier", 8, 12
    )

    y = y - hash_box_h - SECTION_GAP

    # ── 5. Ringkasan Garis Masa / Timeline Summary ──
    if language == "en":
        section5_title = "Timeline Summary"
        label_completed_count = "Completed"
        label_pending_count = "Pending / In Progress"
        label_initial = "Initial Report"
        label_last_update = "Last Update"
    else:
        section5_title = "Ringkasan Garis Masa"
        label_completed_count = "Telah Siap"
        label_pending_count = "Belum Siap"
        label_initial = "Laporan Awal"
        label_last_update = "Kemas Kini Terakhir"

    y = _draw_section(section5_title, [
        (label_completed_count, str(completed)),
        (label_pending_count, str(not_completed)),
        (label_initial, str(generated_date)),
        (label_last_update, formatted_dt),
    ], y)

    # ── Footer note ──
    footer_y = y - 10
    if footer_y > 40:
        pdf.setFont("Helvetica-Oblique", 8)
        if language == "en":
            pdf.drawCentredString(
                width / 2, footer_y,
                "This certificate should be read together with the verification and signature page."
            )
        else:
            pdf.drawCentredString(
                width / 2, footer_y,
                "Sijil ini hendaklah dibaca bersama halaman pengesahan dan tandatangan."
            )

    return y


# ---- Main PDF Generation Function ----

def generate_tribunal_pdf(defects, report_data, language, ai_report_text, labels, evidence_dir, closed_evidence_appendix=None, role="Homeowner", auto_close_days=14, project_name_override=None):
    """
    Generate Tribunal Claim PDF (Borang 1 TTPM format).
    
    Args:
        defects: List of defect dicts (prepared with all calculated fields)
        report_data: Dict with case_info, claimant, respondent, summary_stats
        language: 'en' or 'ms'
        ai_report_text: String of AI-generated report text
        labels: Dict of PDF labels (from PDF_LABELS)
        evidence_dir: Path to evidence directory
        closed_evidence_appendix: Optional list of closed defect info
        role: String role (Homeowner, Developer, Legal)
        auto_close_days: Integer for auto-close days
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Ensure evidence directory exists
    os.makedirs(evidence_dir, exist_ok=True)

    # ============================================
    # PAGE 1: BORANG 1 HEADER & PARTIES
    # ============================================
    
    TOP_MARGIN = 40
    LINE_SPACING_SMALL = 13
    LINE_SPACING_MEDIUM = 16
    LINE_SPACING_LARGE = 22

    y = height - TOP_MARGIN

    # Act Title
    pdf.setFont("Helvetica-Bold", 11)
    if language == "en":
        pdf.drawCentredString(width/2, y, "CONSUMER PROTECTION ACT 1999")
    else:
        pdf.drawCentredString(width/2, y, "AKTA PERLINDUNGAN PENGGUNA 1999")
    
    y -= LINE_SPACING_MEDIUM

    # Regulations Title
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawCentredString(width/2, y, "CONSUMER PROTECTION REGULATIONS")
    else:
        pdf.drawCentredString(width/2, y, "PERATURAN-PERATURAN PERLINDUNGAN PENGGUNA")
    
    y -= LINE_SPACING_SMALL

    # Tribunal Reference
    if language == "en":
        pdf.drawCentredString(width/2, y, "(CONSUMER CLAIMS TRIBUNAL) 1999")
    else:
        pdf.drawCentredString(width/2, y, "(TRIBUNAL TUNTUTAN PENGGUNA) 1999")
    
    y -= LINE_SPACING_LARGE

    # Form Title
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

    # Statement Title
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

    # Location & Claim Number
    pdf.setFont("Helvetica", 10)

    lokasi = str(report_data.get("case_info", {}).get("tribunal_location") or "-").strip().upper()
    negeri = str(report_data.get("case_info", {}).get("state_name") or "-").strip().upper()
    no_tuntutan = report_data.get("case_info", {}).get("claim_number") or "-"

    # FORCEFULLY READ FROM report_data as requested
    project_name = report_data.get("project_name", "-")

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

    # --- Claimant ---
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
    claimant = report_data.get('claimant', {})
    
    # Encrypt NRIC before displaying
    encrypted_nric = encrypt_text(claimant.get('national_id', ''))
    decrypted_nric = decrypt_text(encrypted_nric)
    
    if language == "en":
        y = draw_table_row(pdf, "Claimant Name", 200, 210, claimant.get('name', ''), y, width - 260)
        y = draw_table_row(pdf, "IC/Passport No.", 200, 210, decrypted_nric, y, width - 260)
        y = draw_table_row(pdf, "Correspondence Address", 200, 210, str(claimant.get('address_line_1') or '-').strip(), y, width - 260)
        y = draw_table_row(pdf, "Phone No.", 200, 210, claimant.get('phone_number', ''), y, width - 260)
        y = draw_table_row(pdf, "Fax/Email", 200, 210, claimant.get('email', ''), y, width - 260)
    else:
        y = draw_table_row(pdf, "Nama Pihak Yang Menuntut", 200, 210, claimant.get('name', ''), y, width - 260)
        y = draw_table_row(pdf, "No. Kad Pengenalan/Pasport", 200, 210, decrypted_nric, y, width - 260)
        y = draw_table_row(pdf, "Alamat Surat Menyurat", 200, 210, str(claimant.get('address_line_1') or '-').strip(), y, width - 260)
        y = draw_table_row(pdf, "No. Telefon", 200, 210, claimant.get('phone_number', ''), y, width - 260)
        y = draw_table_row(pdf, "No. Faks/ E-mel", 200, 210, claimant.get('email', ''), y, width - 260)
    
    # --- Respondent ---
    y -= 45
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "RESPONDENT")
    else:
        pdf.drawString(50, y, "PENENTANG")
    
    box_top = y - 10
    box_height = 190
    pdf.rect(box_x, box_top - box_height, box_width, box_height)
    
    y -= 22
    pdf.setFont("Helvetica", 9)
    respondent = report_data.get('respondent', {})
    
    if language == "en":
        y = draw_table_row(pdf, "Name of Respondent/Company/\nCorporation/Organisation/Firm", 200, 210, respondent.get('name', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "Identity Card No./\nCompany Registration No./\nCorporation/Organisation/Firm", 200, 210, respondent.get('registration_no', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "Correspondence Address", 200, 210, respondent.get('address_line_1', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "Telephone No.", 200, 210, respondent.get('phone_number', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "Fax/E-mail", 200, 210, respondent.get('email', ''), y, width - 260)
    else:
        y = draw_table_row(pdf, "Nama Penentang/Syarikat/\nPertubuhan Perbadanan/Firma", 200, 210, respondent.get('name', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "No. Kad Pengenalan/\nNo. Pendaftaran Syarikat/\nPertubuhan Perbadanan/Firma", 200, 210, respondent.get('registration_no', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "Alamat Surat Menyurat", 200, 210, respondent.get('address_line_1', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "No. Telefon", 200, 210, respondent.get('phone_number', ''), y, width - 260)
        y -= 4
        y = draw_table_row(pdf, "No. Faks/E-mel", 200, 210, respondent.get('email', ''), y, width - 260)
    
    y = box_top - box_height - 30
    
    # --- Claim Amount ---
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "STATEMENT OF CLAIM")
        y -= 20
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, "The Claimant's claim is for the amount of RM:")
        claim_amt = str(report_data.get('case_info', {}).get('claim_amount') or '-').replace('RM', '').strip()
        pdf.drawString(280, y, f": {claim_amt}")
    else:
        pdf.drawString(50, y, "PERNYATAAN TUNTUTAN")
        y -= 20
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, "Tuntutan Pihak Yang Menuntut ialah untuk jumlah RM:")
        claim_amt = str(report_data.get('case_info', {}).get('claim_amount') or '-').replace('RM', '').strip()
        pdf.drawString(280, y, f": {claim_amt}")
    
    # --- Claim Details ---
    y -= 30
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Claim Details")
    else:
        pdf.drawString(50, y, "Butir-butir Tuntutan")
    
    box_top = y - 10
    box_height = 75
    pdf.rect(50, box_top - box_height, width - 100, box_height)
    
    y -= 20
    pdf.setFont("Helvetica", 9)
    if language == "en":
        pdf.drawString(60, y, "Goods/Services")
        pdf.drawString(200, y, f": {report_data.get('case_info', {}).get('item_service', 'Defect Repairs During DLP Period')}")
        y -= 15
        pdf.drawString(60, y, "Date of Purchase/Transaction")
        pdf.drawString(200, y, f": {report_data.get('case_info', {}).get('transaction_date', report_data.get('case_info', {}).get('generated_date'))}")
        y -= 15
        pdf.drawString(60, y, "Amount Paid")
        pdf.drawString(200, y, f": RM {report_data.get('case_info', {}).get('claim_amount', '-')}")
        y -= 15
        pdf.drawString(60, y, "Property Location")
        pdf.drawString(200, y, f": {project_name}")
    else:
        pdf.drawString(60, y, "Barangan/Perkhidmatan")
        pdf.drawString(200, y, f": {report_data.get('case_info', {}).get('item_service', 'Pembaikan Kecacatan Dalam Tempoh DLP')}")
        y -= 15
        pdf.drawString(60, y, "Tarikh Pembelian/ Transaksi")
        pdf.drawString(200, y, f": {report_data.get('case_info', {}).get('transaction_date', report_data.get('case_info', {}).get('generated_date'))}")
        y -= 15
        pdf.drawString(60, y, "Jumlah yang dibayar")
        pdf.drawString(200, y, f": RM {report_data.get('case_info', {}).get('claim_amount', '-')}")
        y -= 15
        pdf.drawString(60, y, "Lokasi Harta")
        pdf.drawString(200, y, f": {project_name}")
    
    # ============================================
    # PAGE 2: SUMMARY & DEFECT LIST
    # ============================================
    draw_footer(pdf, width, labels)
    pdf.showPage()
    y = height - 50
    
    # --- Claim Summary ---
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Claim Summary:")
    else:
        pdf.drawString(50, y, "Ringkasan Tuntutan:")
    
    box_top = y - 10
    box_height = 100
    pdf.rect(50, box_top - box_height, width - 100, box_height)
    
    y -= 25
    pdf.setFont("Helvetica", 9)
    summary = report_data.get('summary_stats', {})
    if language == "en":
        pdf.drawString(60, y, f"Total Defects Reported: {summary.get('total_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Pending: {summary.get('pending_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"In Progress: {summary.get('investigation_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Completed: {summary.get('completed_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Overdue: {summary.get('overdue_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Non-Compliant (30-Day HDA): {summary.get('hda_non_compliant_defects', 0)}")
        y -= 15
    else:
        pdf.drawString(60, y, f"Jumlah Kecacatan Dilaporkan: {summary.get('total_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Belum Diselesaikan: {summary.get('pending_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Dalam Tindakan: {summary.get('investigation_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Telah Diselesaikan: {summary.get('completed_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Telah Melebihi Tarikh Siap: {summary.get('overdue_defects', 0)}")
        y -= 15
        pdf.drawString(60, y, f"Tidak Mematuhi Tempoh 30 Hari: {summary.get('hda_non_compliant_defects', 0)}")
        y -= 15
    
    y = box_top - box_height - 20

    if role in ["Homeowner", "Developer", "Legal"] and closed_evidence_appendix:
        pdf.setFont("Helvetica-Oblique", 8)
        if language == "en":
            y = draw_wrapped_text(
                pdf,
                "Note: Closed cases are excluded from the main defect summary and listed in Appendix A.",
                50, y, width - 100, "Helvetica-Oblique", 8, 12
            )
        else:
            y = draw_wrapped_text(
                pdf,
                "Nota: Kes berstatus Ditutup dikecualikan daripada ringkasan utama dan disenaraikan dalam Lampiran A.",
                50, y, width - 100, "Helvetica-Oblique", 8, 12
            )
        y -= 6
    
    # --- Defect List (Card Layout) ---
    y -= 35
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Defect List:")
    else:
        pdf.drawString(50, y, "Senarai Kecacatan:")

    y -= 20
    pdf.setFont("Helvetica", 9)

    for i, defect in enumerate(defects, 1):
        y, _ = draw_defect_card(
            pdf, defect, y, width, language, labels, role, evidence_dir, i, height
        )

    # ============================================
    # AI REPORT SECTION
    # ============================================
    if ai_report_text:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50

        LEFT_MARGIN = 50
        PARAGRAPH_INDENT = 70
        RIGHT_MARGIN = width - 50
        LINE_HEIGHT = 18
        TEXT_WIDTH = RIGHT_MARGIN - PARAGRAPH_INDENT

        pdf.setFont("Helvetica-Bold", 12)
        if language == "en":
            pdf.drawCentredString(width/2, y, "AI-GENERATED CLAIM SUMMARY REPORT")
        else:
            pdf.drawCentredString(width/2, y, "LAPORAN RINGKASAN TUNTUTAN DIJANA AI")
        
        y -= 30

        # Clean AI report text
        clean_text = ai_report_text
        summary_stats = report_data.get("summary_stats", {})

        clean_text = re.sub(
            r"Total number of defects.*?\.",
            f"Total number of defects reported is {summary_stats.get('total_defects',0)}.",
            clean_text
        )
        clean_text = clean_text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
        clean_text = clean_text.replace('\r\n', '\n').replace('\r', '\n')
        clean_text = clean_text.encode("utf-8", "ignore").decode("utf-8")
        
        # Translate status text
        if language == "en":
            clean_text = re.sub(r"Status: Telah Diselesaikan", "Status: Completed", clean_text)
            clean_text = re.sub(r"Status: Belum Diselesaikan", "Status: Pending", clean_text)
            clean_text = re.sub(r"Status: Dalam Tindakan", "Status: In Progress", clean_text)
            clean_text = re.sub(r"Status: Tertangguh", "Status: Delayed", clean_text)
            clean_text = re.sub(r"Status Tertunggak:", "Overdue Status:", clean_text)
            clean_text = re.sub(r"Pematuhan HDA \(30 Hari\):", "HDA Compliance (30 Days):", clean_text)
        else:
            clean_text = re.sub(r"Status: Completed", "Status: Telah Diselesaikan", clean_text)
            clean_text = re.sub(r"Status: Pending", "Status: Belum Diselesaikan", clean_text)
            clean_text = re.sub(r"Status: In Progress", "Status: Dalam Tindakan", clean_text)
            clean_text = re.sub(r"Status: Delayed", "Status: Tertangguh", clean_text)
            clean_text = re.sub(r"Overdue Status:", "Status Tertunggak:", clean_text)
            clean_text = re.sub(r"HDA Compliance \(30 Days\):", "Pematuhan HDA (30 Hari):", clean_text)

        lines = clean_text.split('\n')

        BOTTOM_MARGIN   = 60   # minimum y before forcing a new page
        BODY_LINE_H     = 15   # line height for body / key-value lines
        BULLET_LINE_H   = 14   # line height for bullet lines
        DEFECT_LINE_H   = 15
        BODY_INDENT     = LEFT_MARGIN + 20
        BULLET_INDENT   = LEFT_MARGIN + 28
        KV_LABEL_W      = 130  # approximate width reserved for key label
        KV_VALUE_X      = LEFT_MARGIN + 20 + KV_LABEL_W

        # ── Pattern helpers ───────────────────────────────────────────────
        _re_numbered    = re.compile(r"^(\d+)\.\s+(.+)")
        _re_defect_sub  = re.compile(r"^([a-z])\.\s+((?:Kecacatan|Defect) ID .+)", re.IGNORECASE)
        _re_kv          = re.compile(r"^([^:]{3,40}):\s*(.*)$")
        _re_bullet      = re.compile(r"^[-•]\s+(.+)")

        # ── Page-break helpers ────────────────────────────────────────────
        def _new_page():
            """Emit a page, reset y to top margin."""
            nonlocal y
            draw_footer(pdf, width, labels)
            pdf.showPage()
            y = height - 50

        def _count_wrap_lines(text, font_name, font_size, avail_w):
            """Estimate how many wrapped lines `text` needs."""
            words = text.split()
            if not words:
                return 0
            lines_n, cur = 0, ""
            for word in words:
                candidate = (cur + " " + word).strip()
                if pdf.stringWidth(candidate, font_name, font_size) <= avail_w:
                    cur = candidate
                else:
                    lines_n += 1
                    cur = word
            return lines_n + (1 if cur else 0)

        def _needs_break(extra_lines, line_h, pre_gap=0):
            """Return True if content won't fit without a page break."""
            return (y - pre_gap - extra_lines * line_h) < BOTTOM_MARGIN

        def _draw_wrapped(text, x, avail_w, font_name, font_size, line_h, justify=False):
            """Word-wrap text, splitting cleanly across pages as needed."""
            nonlocal y
            words = text.split()
            cur = ""
            for word in words:
                candidate = (cur + " " + word).strip()
                if pdf.stringWidth(candidate, font_name, font_size) <= avail_w:
                    cur = candidate
                else:
                    if cur:
                        if justify:
                            draw_justified_line(pdf, cur, x, y, avail_w, font_name, font_size)
                        else:
                            pdf.drawString(x, y, cur)
                        y -= line_h
                        if y < BOTTOM_MARGIN:
                            _new_page()
                        pdf.setFont(font_name, font_size)
                    cur = word
            if cur:
                if y < BOTTOM_MARGIN:
                    _new_page()
                    pdf.setFont(font_name, font_size)
                pdf.drawString(x, y, cur)
                y -= line_h
                if y < BOTTOM_MARGIN:
                    _new_page()
                pdf.setFont(font_name, font_size)

        # ── Main rendering loop ───────────────────────────────────────────
        for raw_line in lines:
            stripped = raw_line.strip()

            # ── Blank line → tiny gap (never forces page break alone) ─────
            if not stripped:
                if y - 5 >= BOTTOM_MARGIN:
                    y -= 5
                continue

            # ── Numbered section header (e.g. "1. Tujuan Laporan") ────────
            m_num = _re_numbered.match(stripped)
            if m_num:
                # Need room for: gap(10) + header(16) + at least 1 body line(15)
                required = 10 + 16 + BODY_LINE_H
                if _needs_break(1, required):
                    _new_page()
                else:
                    y -= 10  # breathing space only when staying on same page
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(LEFT_MARGIN, y, f"{m_num.group(1)}. {m_num.group(2)}")
                y -= 16
                if y < BOTTOM_MARGIN:
                    _new_page()
                pdf.setFont("Helvetica", 9)
                continue

            # ── Defect sub-header (e.g. "a. Kecacatan ID 5:") ─────────────
            m_def = _re_defect_sub.match(stripped)
            if m_def:
                # Need room for: gap(8) + sub-header(14) + at least 2 field lines(15 each)
                required = 8 + 14 + 2 * DEFECT_LINE_H
                if _needs_break(1, required):
                    _new_page()
                else:
                    y -= 8
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(LEFT_MARGIN + 10, y, stripped)
                y -= 14
                if y < BOTTOM_MARGIN:
                    _new_page()
                pdf.setFont("Helvetica", 9)
                continue

            # ── Bullet line (e.g. "- Klasifikasi: …") ─────────────────────
            m_bull = _re_bullet.match(stripped)
            if m_bull:
                bullet_text = "•  " + m_bull.group(1)
                avail = RIGHT_MARGIN - BULLET_INDENT
                n = _count_wrap_lines(bullet_text, "Helvetica", 9, avail)
                if _needs_break(n, BULLET_LINE_H):
                    _new_page()
                pdf.setFont("Helvetica", 9)
                _draw_wrapped(bullet_text, BULLET_INDENT, avail, "Helvetica", 9, BULLET_LINE_H)
                continue

            # ── Key-Value pair (e.g. "Unit : Bandar Seri …") ──────────────
            m_kv = _re_kv.match(stripped)
            if m_kv:
                key_raw = m_kv.group(1).strip()
                val_raw = (m_kv.group(2) or "").strip()

                # ── Special case: value is a bullet (e.g. "Ulasan: - Klasifikasi: …")
                # Draw the label on its own line, then render the bullet below it.
                if val_raw.startswith("- ") or val_raw.startswith("• "):
                    if _needs_break(2, DEFECT_LINE_H):
                        _new_page()
                    pdf.setFont("Helvetica-Bold", 9)
                    pdf.drawString(BODY_INDENT, y, key_raw + " :")
                    y -= DEFECT_LINE_H  # move to next line before the bullet
                    if y < BOTTOM_MARGIN:
                        _new_page()
                    pdf.setFont("Helvetica", 9)
                    # strip the leading dash and render as bullet
                    bullet_content = val_raw.lstrip("- ").lstrip("• ").strip()
                    bullet_text = "•  " + bullet_content
                    avail_b = RIGHT_MARGIN - BULLET_INDENT
                    _draw_wrapped(bullet_text, BULLET_INDENT, avail_b, "Helvetica", 9, BULLET_LINE_H)
                    continue

                # ── Normal KV: label on left, value on right, same line ───
                avail_kv = RIGHT_MARGIN - KV_VALUE_X
                n_kv = _count_wrap_lines(val_raw, "Helvetica", 9, avail_kv) if val_raw else 1
                if _needs_break(n_kv, DEFECT_LINE_H):
                    _new_page()
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(BODY_INDENT, y, key_raw + " :")
                pdf.setFont("Helvetica", 9)
                if val_raw:
                    words = val_raw.split()
                    cur = ""
                    for word in words:
                        candidate = (cur + " " + word).strip()
                        if pdf.stringWidth(candidate, "Helvetica", 9) <= avail_kv:
                            cur = candidate
                        else:
                            if cur:
                                pdf.drawString(KV_VALUE_X, y, cur)
                                y -= DEFECT_LINE_H
                                if y < BOTTOM_MARGIN:
                                    _new_page()
                                pdf.setFont("Helvetica", 9)
                            cur = word
                    if cur:
                        pdf.drawString(KV_VALUE_X, y, cur)
                        y -= DEFECT_LINE_H
                        if y < BOTTOM_MARGIN:
                            _new_page()
                        pdf.setFont("Helvetica", 9)
                else:
                    pdf.drawString(KV_VALUE_X, y, "-")
                    y -= DEFECT_LINE_H
                    if y < BOTTOM_MARGIN:
                        _new_page()
                    pdf.setFont("Helvetica", 9)
                continue

            # ── Body paragraph (everything else) ──────────────────────────
            avail = RIGHT_MARGIN - BODY_INDENT
            n_body = _count_wrap_lines(stripped, "Helvetica", 9, avail)
            # If the full paragraph fits on this page, keep it together
            if _needs_break(n_body, BODY_LINE_H) and n_body <= 6:
                _new_page()
            pdf.setFont("Helvetica", 9)
            _draw_wrapped(stripped, BODY_INDENT, avail, "Helvetica", 9, BODY_LINE_H, justify=True)


    # ============================================
    # APPENDIX: CLOSED CASE DETAILS (Card Layout)
    # ============================================
    if role in ["Homeowner", "Developer", "Legal", "Admin"] and closed_evidence_appendix:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50

        # Draw appendix header
        pdf.setFont("Helvetica-Bold", 11)
        if language == "en":
            pdf.drawCentredString(width / 2, y, "APPENDIX A: CLOSED CASE DETAILS")
            pdf.setFont("Helvetica", 8)
            pdf.drawCentredString(
                width / 2, y - 14,
                "Closed cases are excluded from the main body and listed here for reference only."
            )
        else:
            pdf.drawCentredString(width / 2, y, "LAMPIRAN A: BUTIRAN KES DITUTUP")
            pdf.setFont("Helvetica", 8)
            pdf.drawCentredString(
                width / 2, y - 14,
                "Kes ditutup dikecualikan daripada badan laporan utama dan disenaraikan di sini untuk rujukan sahaja."
            )
        y -= 35

        for j, item in enumerate(closed_evidence_appendix, 1):
            closed_days = calculate_days_to_complete(
                item.get("reported_date"), item.get("completed_date")
            )
            days_str = str(closed_days) if closed_days is not None else "-"

            if language == "en":
                closed_rule_text = f"Closed after {auto_close_days} days from completion"
                uploaded_text = f"Uploaded: {format_pdf_date(item.get('uploaded_at'))}"
            else:
                closed_rule_text = f"Ditutup selepas {auto_close_days} hari dari tarikh siap"
                uploaded_text = f"Muat Naik: {format_pdf_date(item.get('uploaded_at'))}"

            extra_fields = [
                ("Closed Rule", closed_rule_text),
                ("Uploaded", format_pdf_date(item.get("uploaded_at"))),
            ]

            appendix_defect = {
                "id": item.get("id"),
                "desc": "",
                "unit": item.get("unit", "-"),
                "status": "Closed",
                "reported_date": item.get("reported_date"),
                "deadline": "-",
                "completed_date": item.get("completed_date"),
                "hda_compliant": item.get("hda_compliant", True),
                "is_overdue": False,
                "priority": "",
                "remarks": "",
                "evidence_filename": item.get("filename"),
                "evidence_file_path": item.get("file_path"),
            }
            y, _ = draw_defect_card(
                pdf, appendix_defect, y, width, language, labels, role,
                evidence_dir, j, height, extra_fields=extra_fields
            )

    # ============================================
    # SIGNATURE & METERAI
    # ============================================
    draw_footer(pdf, width, labels)
    pdf.showPage()
    y = height - 50

    pdf.setFont("Helvetica-Bold", 11)
    if language == "en":
        pdf.drawCentredString(width / 2, y, "Verification and Signature")
    else:
        pdf.drawCentredString(width / 2, y, "Pengesahan dan Tandatangan")
    
    y -= 90

    pdf.setFont("Helvetica", 9)

    short_line = "." * 55
    long_line = "." * 90

    short_width = pdf.stringWidth(short_line, "Helvetica", 9)
    long_width = pdf.stringWidth(long_line, "Helvetica", 9)

    left_x = 50
    right_x = width - 50 - long_width

    left_center = left_x + (short_width / 2)
    right_center = right_x + (long_width / 2)

    # Row 1
    pdf.drawString(left_x, y, short_line)
    pdf.drawString(right_x, y, long_line)
    y -= 20
    if language == "en":
        pdf.drawCentredString(left_center, y, "Date")
        pdf.drawCentredString(right_center, y, "Signature/Thumbprint of Claimant")
    else:
        pdf.drawCentredString(left_center, y, "Tarikh")
        pdf.drawCentredString(right_center, y, "Tandatangan/Cap ibu jari Pihak Yang Menuntut")
    
    y -= 90

    # Row 2
    pdf.drawString(left_x, y, short_line)
    pdf.drawString(right_x, y, long_line)
    y -= 20
    if language == "en":
        pdf.drawCentredString(left_center, y, "Filing Date")
        pdf.drawCentredString(right_center, y, "Secretary/Tribunal Officer")
    else:
        pdf.drawCentredString(left_center, y, "Tarikh Pemfailan")
        pdf.drawCentredString(right_center, y, "Setiausaha/Pegawai Tribunal")
    
    y -= 100
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawCentredString(width / 2, y, "(SEAL)")
    else:
        pdf.drawCentredString(width / 2, y, "(METERAI)")

    # Filename
    if role == "Legal":
        filename = labels.get("legal_filename", "legal_report.pdf")
    elif role == "Developer":
        filename = labels.get("developer_filename", "developer_report.pdf")
    else:
        filename = labels.get("homeowner_filename", "homeowner_report.pdf")

    # PDF metadata
    pdf.setTitle(os.path.splitext(filename)[0])
    pdf.setAuthor("Automated Compliance Report Generation")
    pdf.setSubject("Tribunal Compliance Report")

    # Digital Validation Hash (computed from report_data for integrity)
    report_string = json.dumps(report_data, sort_keys=True)
    digital_hash = hashlib.sha256(report_string.encode()).hexdigest()

    # Finalise the signature page before moving to certificate
    draw_footer(pdf, width, labels)

    # ============================================
    # CERTIFICATE PAGE (final summary page)
    # ============================================
    render_certificate_page(pdf, width, height, report_data, labels, language, digital_hash)

    pdf.save()
    buffer.seek(0)

    return buffer, filename
