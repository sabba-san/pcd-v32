"""
One-time script: migrate all existing defect/evidence image files from disk
into the `image_data` Base64 column in the database.

Run this BEFORE redeploying to DigitalOcean so existing images survive
the ephemeral filesystem wipe.

Usage:
    python scripts/migrate_images_to_db.py
"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Defect, Evidence

app = create_app()

with app.app_context():
    migrated_defects = 0
    migrated_evidence = 0

    # ── Migrate Defect images ────────────────────────────────────────────────
    defects = Defect.query.filter(
        Defect.image_data.is_(None),
        Defect.image_path.isnot(None),
        Defect.image_path != '',
    ).all()

    for defect in defects:
        for base_dir in [
            os.path.join(app.root_path, 'evidence'),
            os.path.join(app.instance_path, 'uploads', 'upload_data'),
        ]:
            candidate = os.path.join(base_dir, defect.image_path)
            if os.path.exists(candidate):
                with open(candidate, 'rb') as f:
                    defect.image_data = base64.b64encode(f.read()).decode('utf-8')
                migrated_defects += 1
                break

    # ── Migrate Evidence images ──────────────────────────────────────────────
    evidence_records = Evidence.query.filter(
        Evidence.image_data.is_(None),
        Evidence.file_path.isnot(None),
        Evidence.file_path != '',
    ).all()

    for ev in evidence_records:
        evidence_dir = os.path.join(app.root_path, 'evidence')
        candidate = os.path.join(evidence_dir, ev.file_path)
        if os.path.exists(candidate):
            with open(candidate, 'rb') as f:
                ev.image_data = base64.b64encode(f.read()).decode('utf-8')
            migrated_evidence += 1

    db.session.commit()

    print(f"Migrated {migrated_defects} defect images and {migrated_evidence} evidence images to database.")
    print("Done.")
