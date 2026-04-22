# module2/routes.py
import glob
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import List, Optional, Set, Tuple

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Defect, Scan
from .utils import load_upload_metadata, upload_root, metadata_path, scan_metadata_path
from .pdf_utils import extract_pdf_images
from .glb_snapshot import extract_snapshots

from ..chatbot_component.dlp_knowledge_base import DLP_RULES

module2 = Blueprint('module2', __name__)

# ── Upload & Processing helpers ───────────────────────────────────────────────

ALLOWED_GLB_EXT = {".glb"}
ALLOWED_PDF_EXT = {".pdf"}
METADATA_FILENAME = "latest_upload.json"


def _default_deadline_date(reported_at: datetime | None = None):
    base = reported_at or datetime.now(timezone.utc)
    return (base + timedelta(days=30)).date()


def _parse_deadline_value(raw_value, reported_at: datetime | None = None):
    value = str(raw_value or "").strip()
    if not value:
        return _default_deadline_date(reported_at)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _allowed_file(filename: str, allowed_exts) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_exts


def _validate_file_magic(filepath: str, expected_magic: bytes) -> bool:
    try:
        with open(filepath, 'rb') as f:
            header = f.read(len(expected_magic))
        return header == expected_magic
    except (OSError, IOError):
        return False


def _persist_upload_metadata(payload: dict) -> None:
    root = upload_root()
    os.makedirs(root, exist_ok=True)
    with open(metadata_path(), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _save_scan_metadata(scan_id: int, meta: dict) -> None:
    path = scan_metadata_path(scan_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

def _tokenize_text(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _auto_assign_images(metadata: dict, defects: List[Defect]) -> bool:
    if not metadata or not defects:
        return False

    assignments = metadata.setdefault("assignments", {}).setdefault("defect_to_image", {})
    images = metadata.get("images", [])
    if not images:
        return False

    assigned = False
    used_images: Set[str] = set()

    def _assign(defect_id: str, image_id: str) -> None:
        nonlocal assigned
        assignments[defect_id] = image_id
        used_images.add(image_id)
        assigned = True

    defect_tokens: dict[str, Set[str]] = {}
    for defect in defects:
        key = str(defect.id)
        # Tokenize id, description, and element for robust matching
        defect_tokens[key] = (
            _tokenize_text(str(defect.id))
            | _tokenize_text(getattr(defect, "description", ""))
            | _tokenize_text(getattr(defect, "element", ""))
        )

    # 1. Exact string matching against snapshot name in the filename
    for image in images:
        image_id = str(image.get("id", ""))
        if not image_id or image_id in used_images:
            continue
        filename = (image.get("file") or "").lower()
        for defect in defects:
            defect_id = str(defect.id)
            if not defect_id or defect_id in assignments:
                continue
            desc = getattr(defect, "description", "").lower()
            if desc and desc in filename:
                _assign(defect_id, image_id)
                break

    # 2. Token overlap logic using filename and page_text
    for image in images:
        image_id = str(image.get("id", ""))
        if not image_id or image_id in used_images:
            continue
        # Tokens from filename + text extracted from the PDF page
        image_tokens = _tokenize_text(image.get("file")) | _tokenize_text(image.get("page_text"))
        if not image_tokens:
            continue
        for defect in defects:
            defect_id = str(defect.id)
            if not defect_id or defect_id in assignments:
                continue
            if defect_tokens.get(defect_id) and image_tokens & defect_tokens[defect_id]:
                _assign(defect_id, image_id)
                break

    # 3. Greedy fallback: pair any remaining sequentially
    remaining_images = [img for img in images if str(img.get("id", "")) not in used_images]
    remaining_defects = [defect for defect in defects if str(defect.id) not in assignments]
    for image, defect in zip(remaining_images, remaining_defects):
        image_id = str(image.get("id", ""))
        defect_id = str(defect.id)
        if image_id and defect_id:
            _assign(defect_id, image_id)

    return assigned

@module2.route('/dlp_info', methods=['GET'])
def dlp_info():
    return jsonify(DLP_RULES)

# --- Lidar Defect Management Routes ---

@module2.route('/projects', methods=['GET'])
@login_required
def list_projects():
    """List all scans/projects in the database"""
    scans = Scan.query.order_by(Scan.created_at.desc()).all()
    
    projects = []
    for scan in scans:
        defect_count = Defect.query.filter_by(scan_id=scan.id).count()
        metadata = load_upload_metadata(scan.id)
        
        projects.append({
            'id': scan.id,
            'name': scan.name,
            'created_at': scan.created_at,
            'defect_count': defect_count,
            'model_path': scan.model_path,
            'metadata': metadata
        })
    
    return render_template('module2/projects.html', projects=projects)

@module2.route('/scans/<int:scan_id>/visualize', methods=['GET'])
@login_required
def visualize_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    model_url = url_for('module2.serve_model', scan_id=scan_id) if scan.model_path else None
    
    upload_metadata = load_upload_metadata(scan_id)
    
    return render_template('module2/visualization.html', 
                          scan=scan, 
                          scan_id=scan_id, 
                          model_url=model_url, 
                          defects=defects,
                          upload_metadata=upload_metadata)

@module2.route('/scans/<int:scan_id>/defects', methods=['GET'])
@login_required
def get_scan_defects(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    
    metadata = load_upload_metadata(scan_id)
    upload_date = metadata.get('scan_date') if metadata else None
    
    defect_list = [{
        'defectId': d.id,
        'x': d.x,
        'y': d.y,
        'z': d.z,
        'element': d.element,
        'location': d.location,
        'defect_type': d.defect_type,
        'severity': d.severity,
        'status': d.status,
        'description': d.description,
        'created_at': upload_date if upload_date else (d.created_at.strftime('%Y-%m-%d') if d.created_at else None)
    } for d in defects]
    return jsonify(defect_list)

@module2.route('/defect/<int:defect_id>', methods=['GET'])
@login_required
def get_defect_details(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    image_url = None
    if defect.image_path:
        image_url = url_for('module2.serve_defect_image', defect_id=defect_id)
    return jsonify({
        'id': defect.id,
        'element': defect.element,
        'location': defect.location,
        'defect_type': defect.defect_type,
        'severity': defect.severity,
        'description': defect.description,
        'x': defect.x,
        'y': defect.y,
        'z': defect.z,
        'status': defect.status,
        'imageUrl': image_url,
        'notes': defect.notes
    })

@module2.route('/defect/<int:defect_id>/status', methods=['PUT'])
@login_required
def update_defect_status(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    data = request.get_json()
    # Note: Lidar code checked current_user.role == 'developer'. In pcd-v32, the attribute is user_type
    if 'status' in data and current_user.user_type == 'developer':
        defect.status = data['status']
    if 'notes' in data:
        defect.notes = data['notes']
    if 'location' in data:
        defect.location = data['location']
    if 'defect_type' in data:
        defect.defect_type = data['defect_type']
    if 'severity' in data:
        defect.severity = data['severity']
    db.session.commit()
    return jsonify({'message': 'Defect updated successfully', 'status': defect.status})

@module2.route('/defect/<int:defect_id>', methods=['DELETE'])
@login_required
def delete_defect(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    db.session.delete(defect)
    db.session.commit()
    return jsonify({'message': 'Defect deleted successfully'})

@module2.route('/scans/<int:scan_id>/defects', methods=['POST'])
@login_required
def create_defect(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    data = request.get_json()
    reported_at = datetime.now(timezone.utc)
    deadline = _parse_deadline_value(data.get('deadline'), reported_at)
    if deadline is None:
        return jsonify({'error': 'Invalid deadline date format. Use YYYY-MM-DD.'}), 400
    defect = Defect(
        scan_id=scan_id,
        x=data.get('x', 0),
        y=data.get('y', 0),
        z=data.get('z', 0),
        element=data.get('element', ''),
        location=data.get('location', ''),
        defect_type=data.get('defect_type', 'Unknown'),
        severity=data.get('severity', 'Medium'),
        description=data.get('description', ''),
        status=data.get('status', 'Reported'),
        notes=data.get('notes', ''),
        reported_date=reported_at,
        deadline=deadline,
    )
    db.session.add(defect)
    db.session.commit()
    return jsonify({'message': 'Defect created', 'defectId': defect.id}), 201


ALLOWED_EVIDENCE_EXTS = {'.jpg', '.jpeg', '.png', '.pdf'}

@module2.route('/scans/<int:scan_id>/report_defect', methods=['POST'])
@login_required
def report_defect(scan_id):
    """Homeowner pinpoint-defect submission with optional photographic evidence."""
    scan = Scan.query.get_or_404(scan_id)

    # ── Coordinates (from hidden form fields set by Babylon.js) ─────────────
    try:
        x = float(request.form.get('x', 0))
        y = float(request.form.get('y', 0))
        z = float(request.form.get('z', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinate values.'}), 400

    element     = request.form.get('element', '').strip()
    description = request.form.get('description', '').strip()
    defect_type = request.form.get('defect_type', 'Unknown').strip()
    severity    = request.form.get('severity', 'Medium').strip()
    location    = request.form.get('location', '').strip()
    notes       = request.form.get('notes', '').strip()
    reported_at = datetime.now(timezone.utc)
    deadline = _parse_deadline_value(request.form.get('deadline'), reported_at)

    if not description:
        return jsonify({'error': 'Defect description is required.'}), 400
    if deadline is None:
        return jsonify({'error': 'Invalid deadline date format. Use YYYY-MM-DD.'}), 400

    # ── Optional photographic evidence upload ────────────────────────────────
    image_path = None
    evidence_file = request.files.get('evidence_image')
    if evidence_file and evidence_file.filename:
        _, ext = os.path.splitext(evidence_file.filename.lower())
        if ext not in ALLOWED_EVIDENCE_EXTS:
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EVIDENCE_EXTS)}'}), 400

        import uuid
        safe_name   = secure_filename(evidence_file.filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        evidence_dir = os.path.join(
            current_app.instance_path, 'uploads', 'upload_data', 'evidence'
        )
        os.makedirs(evidence_dir, exist_ok=True)
        save_path = os.path.join(evidence_dir, unique_name)
        evidence_file.save(save_path)
        # Store relative path so it can be served back via serve_defect_image
        image_path = os.path.join('evidence', unique_name)

    # ── Persist defect record ────────────────────────────────────────────────
    defect = Defect(
        scan_id=scan_id,
        user_id=current_user.id,
        x=x,
        y=y,
        z=z,
        element=element,
        location=location,
        defect_type=defect_type,
        severity=severity,
        description=description,
        status='Reported',
        notes=notes,
        image_path=image_path,
        reported_date=reported_at,
        deadline=deadline,
    )
    db.session.add(defect)
    db.session.commit()

    image_url = url_for('module2.serve_defect_image', defect_id=defect.id) if image_path else None

    return jsonify({
        'message': 'Defect reported successfully.',
        'defect': {
            'id':          defect.id,
            'x':           defect.x,
            'y':           defect.y,
            'z':           defect.z,
            'element':     defect.element,
            'description': defect.description,
            'defect_type': defect.defect_type,
            'severity':    defect.severity,
            'status':      defect.status,
            'imageUrl':    image_url,
        }
    }), 201

@module2.route('/scans/<int:scan_id>/model', methods=['GET'])
@login_required
def serve_model(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    if not scan.model_path:
        abort(404)
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'upload_data')
    response = send_from_directory(upload_dir, scan.model_path)
    response.headers['Content-Type'] = 'model/gltf-binary'
    return response

@module2.route('/defects/image/<int:defect_id>', methods=['GET'])
@login_required
def serve_defect_image(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    if not defect.image_path:
        abort(404)
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'upload_data')
    return send_from_directory(upload_dir, defect.image_path)


# ── Legal Human-in-the-Loop Evidence Review ───────────────────────────────────

@module2.route('/legal/evidence_review', methods=['GET'])
@login_required
def legal_evidence_review():
    """Render the Manual Evidence Review page for the Lawyer role."""
    if current_user.user_type not in ('lawyer', 'legal', 'admin'):
        abort(403)

    # Fetch all defects that have a photographic evidence image attached.
    # Lawyers can review both unverified and already-verified defects.
    defects_with_evidence = Defect.query.filter(
        Defect.image_path.isnot(None),
        Defect.image_path != '',
    ).order_by(Defect.is_verified.asc(), Defect.created_at.desc()).all()

    # Build lightweight dicts to pass to the template (avoids lazy-load issues)
    defect_data = []
    for d in defects_with_evidence:
        defect_data.append({
            'id': d.id,
            'defect_type': d.defect_type or 'Unknown',
            'severity': d.severity or 'Medium',
            'description': d.description or '',
            'location': d.location or '',
            'element': d.element or '',
            'status': d.status or 'Reported',
            'is_verified': d.is_verified,
            'legal_remarks': d.legal_remarks or '',
            'image_url': url_for('module2.serve_defect_image', defect_id=d.id),
        })

    pending_count = sum(1 for d in defect_data if not d['is_verified'])
    verified_count = len(defect_data) - pending_count

    return render_template(
        'role/legal/evidence_review.html',
        defects=defect_data,
        pending_count=pending_count,
        verified_count=verified_count,
    )


@module2.route('/api/legal/verify_defect/<int:defect_id>', methods=['POST'])
@login_required
def api_legal_verify_defect(defect_id):
    """API endpoint: Lawyer manually verifies / overrides a defect's AI assessment."""
    if current_user.user_type not in ('lawyer', 'legal', 'admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    defect = Defect.query.get_or_404(defect_id)
    payload = request.get_json(silent=True) or {}

    manual_severity    = (payload.get('manual_severity') or '').strip()
    manual_defect_type = (payload.get('manual_defect_type') or '').strip()
    legal_remarks_val  = (payload.get('legal_remarks') or '').strip()

    VALID_SEVERITIES   = {'Low', 'Medium', 'High', 'Critical'}
    VALID_DEFECT_TYPES = {'Unknown', 'Crack', 'Water Damage', 'Structural', 'Finish', 'Electrical', 'Plumbing'}

    if manual_severity and manual_severity not in VALID_SEVERITIES:
        return jsonify({'error': f'Invalid severity: {manual_severity}'}), 400
    if manual_defect_type and manual_defect_type not in VALID_DEFECT_TYPES:
        return jsonify({'error': f'Invalid defect type: {manual_defect_type}'}), 400

    if manual_severity:
        defect.severity = manual_severity
    if manual_defect_type:
        defect.defect_type = manual_defect_type
    if legal_remarks_val:
        defect.legal_remarks = legal_remarks_val

    defect.is_verified    = True
    defect.verified_by_id = current_user.id

    db.session.commit()

    return jsonify({
        'success': True,
        'defect_id': defect.id,
        'severity': defect.severity,
        'defect_type': defect.defect_type,
        'is_verified': defect.is_verified,
    })


@module2.route('/project/<int:scan_id>', methods=['GET'])
@login_required
def view_project(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    model_url = url_for('module2.serve_model', scan_id=scan_id) if scan.model_path else None
    
    upload_metadata = load_upload_metadata(scan_id)
    
    return render_template('module2/project_detail.html', 
                          scan=scan, 
                          scan_id=scan_id, 
                          model_url=model_url, 
                          defects=defects,
                          upload_metadata=upload_metadata)


# ── Upload & Process Routes ────────────────────────────────────────────────────

@module2.route('/upload-scan', methods=['GET', 'POST'])
@login_required
def upload_scan():
    """Upload a new 3D GLB model + PDF report and commit to the database."""
    if request.method == 'GET':
        return render_template('module2/upload.html')

    try:
        glb_file  = request.files.get('glb_model')
        pdf_file  = request.files.get('pdf_report')
        project_name = request.form.get('project_name', '').strip()
        scan_date    = request.form.get('scan_date', '')
        address      = request.form.get('address', '')
        unit_no      = request.form.get('unit_no', '')
        latitude     = request.form.get('latitude', '')
        longitude    = request.form.get('longitude', '')
        notes        = request.form.get('notes', '')

        if not glb_file or glb_file.filename == '':
            flash('Please upload a GLB 3D model file.', 'error')
            return redirect(request.url)

        if not _allowed_file(glb_file.filename, ALLOWED_GLB_EXT):
            flash('Invalid file type. Only .glb is allowed.', 'error')
            return redirect(request.url)

        root = upload_root()
        os.makedirs(root, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        glb_name  = secure_filename(glb_file.filename)
        glb_path  = os.path.join(root, glb_name)
        glb_file.save(glb_path)

        if not _validate_file_magic(glb_path, b'glTF'):
            os.remove(glb_path)
            flash('Invalid GLB file content. The file does not appear to be a valid 3D model.', 'error')
            return redirect(request.url)

        upload_id = f'upload_{timestamp}'
        image_dir_name = f'{upload_id}_images'
        image_dir = os.path.join(root, image_dir_name)
        extracted_images = []

        # Handle optional PDF
        pdf_name = None
        if pdf_file and pdf_file.filename and _allowed_file(pdf_file.filename, ALLOWED_PDF_EXT):
            pdf_name = secure_filename(pdf_file.filename)
            pdf_path = os.path.join(root, pdf_name)
            pdf_file.save(pdf_path)
            if not _validate_file_magic(pdf_path, b'%PDF'):
                os.remove(pdf_path)
                pdf_name = None
            else:
                try:
                    extracted_images = extract_pdf_images(pdf_path, image_dir)
                except Exception as e:
                    current_app.logger.warning("Failed to extract PDF images: %s", e)

        # Extract Snapshot defects from GLB
        try:
            snapshots = extract_snapshots(glb_path)
        except Exception as exc:
            current_app.logger.warning("GLB snapshot extraction failed: %s", exc)
            snapshots = []

        # Create Scan record
        scan_label = project_name or f'Scan {timestamp}'
        scan = Scan(name=scan_label, model_path=glb_name)
        db.session.add(scan)
        db.session.flush()  # get scan.id before commit

        # Create Defect records from snapshots
        db_defects = []
        for snap in snapshots:
            reported_at = datetime.now(timezone.utc)
            defect = Defect(
                scan_id=scan.id,
                x=float(snap.coordinates[0]),
                y=float(snap.coordinates[1]),
                z=float(snap.coordinates[2]),
                element=snap.element or '',
                description=snap.label or snap.snapshot_id or '',
                defect_type='Unknown',
                severity='Medium',
                status='Reported',
                reported_date=reported_at,
                deadline=_default_deadline_date(reported_at),
            )
            db.session.add(defect)
            db_defects.append(defect)

        db.session.flush() # ensure defect IDs are present

        # Persist metadata for visualization
        meta = {
            'id': upload_id,
            'created_at': timestamp,
            'project_name': project_name,
            'scan_date': scan_date,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'unit_no': unit_no,
            'glb_path': glb_path,
            'pdf_path': pdf_name,
            'image_dir': image_dir_name if extracted_images else None,
            'images': extracted_images,
            'assignments': {'defect_to_image': {}},
            'notes': notes,
        }

        # Auto-assign extracted images to the defects
        if extracted_images and db_defects:
            _auto_assign_images(meta, db_defects)
            # Update database with assigned image paths
            assignments = meta.get('assignments', {}).get('defect_to_image', {})
            for defect in db_defects:
                assigned_img_id = assignments.get(str(defect.id))
                if assigned_img_id:
                    # Find the physical image file
                    for img in extracted_images:
                        if img.get("id") == assigned_img_id:
                            defect.image_path = os.path.join(image_dir_name, img.get("file", ""))
                            break

        db.session.commit()

        _persist_upload_metadata(meta)
        _save_scan_metadata(scan.id, meta)

        if extracted_images:
            flash(f'Project "{scan_label}" uploaded. Detected {len(snapshots)} defects and successfully extracted {len(extracted_images)} images from PDF.', 'success')
        else:
            flash(f'Project "{scan_label}" uploaded successfully with {len(snapshots)} defects detected.', 'success')
        return redirect(url_for('module2.list_projects'))

    except Exception as exc:
        current_app.logger.error('Upload error: %s', exc)
        db.session.rollback()
        flash(f'An error occurred: {exc}', 'error')
        return redirect(request.url)
