# module2/routes.py
import glob
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Defect, Scan
from .utils import load_upload_metadata, upload_root, metadata_path, scan_metadata_path

from ..chatbot_component.dlp_knowledge_base import DLP_RULES

module2 = Blueprint('module2', __name__)

# ── Upload & Processing helpers ───────────────────────────────────────────────

ALLOWED_GLB_EXT = {".glb"}
ALLOWED_PDF_EXT = {".pdf"}
METADATA_FILENAME = "latest_upload.json"


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


def _extract_snapshots_from_glb(glb_path: str) -> list:
    """Extract snapshot metadata from a GLB, returns list of dicts."""
    try:
        from pygltflib import GLTF2
        gltf = GLTF2().load(glb_path)
        snapshots = []
        for i, node in enumerate(gltf.nodes or []):
            name = (node.name or "").lower()
            if "snapshot" in name and node.translation:
                snapshots.append({
                    "id": f"Snapshot-{i}",
                    "label": node.name,
                    "element": node.name,
                    "coordinates": {
                        "x": node.translation[0],
                        "y": node.translation[1],
                        "z": node.translation[2],
                    }
                })
        return snapshots
    except Exception as exc:
        current_app.logger.warning("GLB snapshot extraction failed: %s", exc)
        return []

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
        notes=data.get('notes', '')
    )
    db.session.add(defect)
    db.session.commit()
    return jsonify({'message': 'Defect created', 'defectId': defect.id}), 201

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

        # Handle optional PDF
        pdf_name = None
        if pdf_file and pdf_file.filename and _allowed_file(pdf_file.filename, ALLOWED_PDF_EXT):
            pdf_name = secure_filename(pdf_file.filename)
            pdf_path = os.path.join(root, pdf_name)
            pdf_file.save(pdf_path)
            if not _validate_file_magic(pdf_path, b'%PDF'):
                os.remove(pdf_path)
                pdf_name = None

        # Extract Snapshot defects from GLB
        snapshots = _extract_snapshots_from_glb(glb_path)

        # Create Scan record
        scan_label = project_name or f'Scan {timestamp}'
        scan = Scan(name=scan_label, model_path=glb_name)
        db.session.add(scan)
        db.session.flush()  # get scan.id before commit

        # Create Defect records from snapshots
        for snap in snapshots:
            coords = snap.get('coordinates', {})
            defect = Defect(
                scan_id=scan.id,
                x=float(coords.get('x', 0)),
                y=float(coords.get('y', 0)),
                z=float(coords.get('z', 0)),
                element=snap.get('element', ''),
                description=snap.get('label', ''),
                defect_type='Unknown',
                severity='Medium',
                status='Reported',
            )
            db.session.add(defect)

        db.session.commit()

        # Persist metadata for visualization
        meta = {
            'id': f'upload_{timestamp}',
            'created_at': timestamp,
            'project_name': project_name,
            'scan_date': scan_date,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'unit_no': unit_no,
            'glb_path': glb_path,
            'pdf_path': pdf_name,
            'notes': notes,
        }
        _persist_upload_metadata(meta)
        _save_scan_metadata(scan.id, meta)

        flash(f'Project "{scan_label}" uploaded successfully with {len(snapshots)} defects detected.', 'success')
        return redirect(url_for('module2.list_projects'))

    except Exception as exc:
        current_app.logger.error('Upload error: %s', exc)
        db.session.rollback()
        flash(f'An error occurred: {exc}', 'error')
        return redirect(request.url)