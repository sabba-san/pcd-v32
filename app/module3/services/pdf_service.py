"""
PDF generation service for Tribunal claim forms (Borang 1 TTPM).
Extracted from module3/routes.py to reduce controller bloat.
"""
import os
import re
import json
import hashlib
import base64
from io import BytesIO
from datetime import datetime

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
    
    # --- Defect List ---
    y -= 35
    pdf.setFont("Helvetica-Bold", 10)
    if language == "en":
        pdf.drawString(50, y, "Defect List:")
    else:
        pdf.drawString(50, y, "Senarai Kecacatan:")
    
    y -= 20
    pdf.setFont("Helvetica", 9)

    for i, defect in enumerate(defects, 1):
        HEADER_X = 50
        LABEL_X = 70
        VALUE_X = 220
        RIGHT_MARGIN = 50
        TEXT_WIDTH = width - VALUE_X - RIGHT_MARGIN

        # Estimate height needed
        desc_lines = _estimate_wrapped_lines_with_font(pdf, f": {defect.get('desc', '-')}", "Helvetica", 9, TEXT_WIDTH)
        
        estimated_height = 0
        estimated_height += 16
        estimated_height += desc_lines * 14
        estimated_height += 14 * 7
        if defect.get("priority"):
            estimated_height += 14
        if role == "homeowner" and defect.get("remarks"):
            estimated_height += 14 * 3
        if _resolve_evidence_image_path(evidence_dir, defect.get("id"), defect.get("evidence_filename")):
            estimated_height += 140
        estimated_height += 25

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

        # Defect Header
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(HEADER_X, y, f"{chr(64+i) if i <= 26 else chr(64 + (i % 26))}. {labels.get('defect_id', 'Defect ID')} {defect.get('id', '')}:")
        y -= 16

        pdf.setFont("Helvetica", 9)

        # Description
        pdf.drawString(LABEL_X, y, labels.get('description', 'Description'))
        y = draw_wrapped_text(pdf, f": {defect.get('desc', '-')}", VALUE_X, y, TEXT_WIDTH)

        # Unit
        pdf.drawString(LABEL_X, y, labels.get('unit', 'Unit'))
        pdf.drawString(VALUE_X, y, f": {defect.get('unit', '-')}")
        y -= 14

        # Status
        pdf.drawString(LABEL_X, y, labels.get('status', 'Status'))
        pdf.drawString(VALUE_X, y, f": {defect.get('status', '-')}")
        y -= 14

        # Reported Date
        pdf.drawString(LABEL_X, y, labels.get('reported_date', 'Reported Date'))
        clean_reported_date = format_pdf_date(defect.get('reported_date'))
        pdf.drawString(VALUE_X, y, f": {clean_reported_date}")
        y -= 14

        # Scheduled Completion Date
        pdf.drawString(LABEL_X, y, labels.get('deadline', 'Scheduled Completion Date'))
        pdf.drawString(VALUE_X, y, f": {defect.get('deadline', '-')}")
        y -= 14

        # Actual Completion Date
        pdf.drawString(LABEL_X, y, labels.get('actual_completion_date', 'Actual Completion Date'))
        pdf.drawString(VALUE_X, y, f": {defect.get('completed_date') if defect.get('completed_date') else '-'}")
        y -= 14

        # Days to Complete
        days_to_complete = calculate_days_to_complete(defect.get("reported_date"), defect.get("completed_date"))
        if language == "en":
            pdf.drawString(LABEL_X, y, "Days to Complete")
            pdf.drawString(VALUE_X, y, f": {days_to_complete if days_to_complete is not None else '-'}")
        else:
            pdf.drawString(LABEL_X, y, "Tempoh Siap (Hari)")
            pdf.drawString(VALUE_X, y, f": {days_to_complete if days_to_complete is not None else '-'}")
        y -= 14

        # HDA Compliance
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

        # Overdue
        is_overdue = defect.get("is_overdue", False)
        if language == "en":
            pdf.drawString(LABEL_X, y, "Overdue")
            pdf.drawString(VALUE_X, y, f": {'Yes' if is_overdue else 'No'}")
        else:
            pdf.drawString(LABEL_X, y, "Melebihi Tarikh")
            pdf.drawString(VALUE_X, y, f": {'Ya' if is_overdue else 'Tidak'}")
        y -= 14

        # Priority
        if defect.get("priority"):
            pdf.drawString(LABEL_X, y, labels.get('priority', 'Priority'))
            pdf.drawString(VALUE_X, y, f": {defect['priority']}")
            y -= 14

        # Remarks
        if role == "homeowner" and defect.get("remarks"):
            pdf.drawString(LABEL_X, y, labels.get('remarks', 'Remarks'))
            y = draw_wrapped_text(pdf, f": {defect['remarks']}", VALUE_X, y, TEXT_WIDTH)

        # Evidence Image
        image_path = _resolve_evidence_image_path(evidence_dir, defect.get("id"), defect.get("evidence_filename"))
        
        if not image_path and defect.get("evidence_file_path"):
            raw_fp = defect.get("evidence_file_path", "").strip()
            if raw_fp and _is_valid_image_path(raw_fp):
                static_candidate = os.path.join(evidence_dir, os.path.basename(raw_fp))
                if os.path.exists(static_candidate):
                    image_path = static_candidate

        if not image_path and defect.get("image_path"):
            candidate_path = os.path.join(evidence_dir, os.path.basename(defect.get('image_path', '')))
            if os.path.exists(candidate_path):
                image_path = candidate_path

        if image_path:
            if y < 180:
                draw_footer(pdf, width, labels)
                pdf.showPage()
                y = height - 50

            pdf.setFont("Helvetica-Oblique", 8)
            pdf.drawString(LABEL_X, y, f"{labels.get('evidence', 'Evidence')}:")
            y -= 10

            try:
                pdf.drawImage(ImageReader(image_path), LABEL_X, y - 110, width=200, height=110)
            except Exception:
                pdf.setFont("Helvetica-Oblique", 8)
                pdf.drawString(LABEL_X, y - 10, f"Error: Evidence image not found.")
            
            y -= 125

            upload_time = format_pdf_date(defect.get("evidence_uploaded_at", "-"))
            pdf.setFont("Helvetica", 8)
            if language == "en":
                pdf.drawString(LABEL_X, y - 5, f"Uploaded At: {upload_time}")
            else:
                pdf.drawString(LABEL_X, y - 5, f"Tarikh Muat Naik: {upload_time}")
            
            y -= 15

        y -= 25

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

        prev_line_is_sub_item = False
        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                if y < 80:
                    draw_footer(pdf, width, labels)
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 9)
                y -= 10
                prev_line_is_sub_item = False
                continue

            is_numbered_header = bool(re.match(r"^\d+\.\s+", stripped))
            is_sub_item = bool(re.match(r"^\s*[-•]\s+", stripped)) or (prev_line_is_sub_item and not is_numbered_header)

            if is_numbered_header:
                pdf.setFont("Helvetica-Bold", 9)
                x_pos = LEFT_MARGIN
            elif is_sub_item:
                pdf.setFont("Helvetica-Bold", 9)
                x_pos = LEFT_MARGIN + 20
            else:
                pdf.setFont("Helvetica", 9)
                x_pos = PARAGRAPH_INDENT

            prev_line_is_sub_item = is_sub_item

            words = stripped.split()
            current_line = ""

            for word in words:
                test_line = current_line + " " + word if current_line else word
                if pdf.stringWidth(test_line, "Helvetica", 9) <= TEXT_WIDTH:
                    current_line = test_line
                else:
                    if is_numbered_header:
                        pdf.drawString(x_pos, y, current_line)
                    else:
                        draw_justified_line(pdf, current_line, x_pos, y, TEXT_WIDTH, "Helvetica", 9)
                    
                    y -= LINE_HEIGHT
                    if y < 80:
                        draw_footer(pdf, width, labels)
                        pdf.showPage()
                        y = height - 50
                        pdf.setFont("Helvetica", 9)
                    
                    current_line = word

            if current_line:
                pdf.drawString(x_pos, y, current_line)
                y -= LINE_HEIGHT

    # ============================================
    # APPENDIX: CLOSED CASE DETAILS
    # ============================================
    if role in ["Homeowner", "Developer", "Legal", "Admin"] and closed_evidence_appendix:
        draw_footer(pdf, width, labels)
        pdf.showPage()
        y = height - 50

        appendix_lines = build_closed_appendix_lines(closed_evidence_appendix, language, auto_close_days)
        
        current_appendix_item = None  # Track the current defect's data for image rendering
        
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
                or "APPENDIX A:" in line
                or "LAMPIRAN A:" in line
            )

            if is_header:
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(50, y, line)
                y -= 14
                
                # Extract defect ID from header and lookup the appendix item
                header_match = re.match(r"^(?:[A-Z]|\d+)\.\s+(?:Defect ID|Kecacatan ID)\s+([^:]+):", line)
                if header_match:
                    defect_id_text = header_match.group(1).strip()
                    current_appendix_item = next(
                        (item for item in closed_evidence_appendix if str(item.get("id")) == defect_id_text),
                        None,
                    )
            else:
                pdf.setFont("Helvetica", 9)
                x = 70 if line.startswith(":") else 50
                
                # Check for image markers in the line
                has_image_marker = "[imej]" in line or "[image]" in line
                
                # Clean the text (remove markers)
                display_line = line.replace("[imej]", "").replace("[image]", "")
                y = draw_wrapped_text(pdf, display_line, x, y, width - 100, "Helvetica", 9, 14)
                
                # After appending text, check the flag and draw image if needed
                if has_image_marker and current_appendix_item:
                    appendix_image_path = _resolve_evidence_image_path(
                        evidence_dir,
                        current_appendix_item.get("id"),
                        current_appendix_item.get("filename"),
                    )
                    
                    # Also try file_path from the item
                    if not appendix_image_path and current_appendix_item.get("file_path"):
                        raw_fp = current_appendix_item.get("file_path", "").strip()
                        if raw_fp and _is_valid_image_path(raw_fp):
                            static_candidate = os.path.join(evidence_dir, os.path.basename(raw_fp))
                            if os.path.exists(static_candidate):
                                appendix_image_path = static_candidate
                    
                    if appendix_image_path and os.path.exists(appendix_image_path):
                        if y < 170:
                            draw_footer(pdf, width, labels)
                            pdf.showPage()
                            y = height - 50
                        try:
                            pdf.drawImage(ImageReader(appendix_image_path), 70, y - 95, width=180, height=95)
                            y -= 110
                        except Exception:
                            pdf.setFont("Helvetica-Oblique", 8)
                            pdf.drawString(70, y - 10, "Evidence image not found.")
                            y -= 25

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

    # Digital Validation Hash
    report_string = json.dumps(report_data, sort_keys=True)
    digital_hash = hashlib.sha256(report_string.encode()).hexdigest()

    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(50, 30, f"Digital Validation Hash: {digital_hash}")

    draw_footer(pdf, width, labels)
    pdf.save()
    buffer.seek(0)

    return buffer, filename
