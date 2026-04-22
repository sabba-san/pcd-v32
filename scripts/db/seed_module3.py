#!/usr/bin/env python3
"""
seed_module3.py  –  Seed sample data for Module 3 (Reporting Dashboard)
Inserts a demo homeowner profile and 6 sample defects so Developer / Legal
views have something to display and test report generation with.

Run from the project root:
    docker exec flask_app python /usr/src/app/scripts/db/seed_module3.py
"""
import os, sys
sys.path.insert(0, '/usr/src/app')

import psycopg2

DB_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://user:password@flask_db:5432/flaskdb'
)

def get_conn():
    return psycopg2.connect(DB_URL)

def seed():
    conn = get_conn()
    cur  = conn.cursor()

    # ── 1. Find or create a demo homeowner user ──────────────
    cur.execute("""
        SELECT id FROM users
        WHERE user_type = 'homeowner'
        ORDER BY id ASC LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        homeowner_id = row[0]
        print(f"Using existing homeowner user id={homeowner_id}")
    else:
        cur.execute("""
            INSERT INTO users (user_type, full_name, email, password_hash, role, unit,
                               housing_project, ic_number, correspondence_address)
            VALUES ('homeowner','Aishah Binti Rahman','aishah@demo.my',
                    'pbkdf2:sha256:demo','Homeowner','A-12-3A',
                    'Taman Demo Indah','901234-05-6789','No 12, Jalan Demo, Kuala Lumpur')
            RETURNING id
        """)
        homeowner_id = cur.fetchone()[0]
        print(f"Created demo homeowner user id={homeowner_id}")

    # ── 2. Homeowner profile ─────────────────────────────────
    cur.execute("""
        INSERT INTO report_homeowner_profile
            (homeowner_id, name, ic_number, email, phone_number,
             address, court_location, state_name, claim_amount, item_service)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (homeowner_id) DO UPDATE SET
            name          = EXCLUDED.name,
            court_location= EXCLUDED.court_location,
            state_name    = EXCLUDED.state_name,
            claim_amount  = EXCLUDED.claim_amount,
            item_service  = EXCLUDED.item_service
    """, (
        homeowner_id,
        'Aishah Binti Rahman',
        '901234-05-6789',
        'aishah@demo.my',
        '012-3456789',
        'No 12, Jalan Demo, Kuala Lumpur',
        'Petaling Jaya',
        'Selangor',
        '15000.00',
        'Defect Repair During DLP',
    ))

    # ── 3. Developer / respondent profile ────────────────────
    cur.execute("""
        SELECT id FROM users
        WHERE user_type = 'developer'
        ORDER BY id ASC LIMIT 1
    """)
    drow = cur.fetchone()
    if drow:
        dev_id = drow[0]
        cur.execute("""
            INSERT INTO report_respondent_profile
                (respondent_id, company_name, registration_number, email, phone_number, address)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (respondent_id) DO UPDATE SET
                company_name        = EXCLUDED.company_name,
                registration_number = EXCLUDED.registration_number
        """, (
            dev_id,
            'Syarikat Pemaju Sdn Bhd',
            '1234567-D',
            'developer@demo.my',
            '03-12345678',
            'Lot 5, Jalan Industri, Shah Alam, Selangor',
        ))
        print(f"Upserted respondent profile for dev id={dev_id}")

    # ── 4. Sample defects ────────────────────────────────────
    sample_defects = [
        ('A-12-3A', 'Ceiling leak in master bedroom',    'Pending',     None,         homeowner_id, 'High',   '2026-05-01'),
        ('A-12-3A', 'Hairline crack on living room wall','In Progress', None,         homeowner_id, 'Medium', '2026-04-20'),
        ('B-05-2B', 'Water seepage behind kitchen wall', 'Pending',     None,         homeowner_id, 'High',   '2026-05-10'),
        ('B-05-2B', 'Defective door frame – bedroom 2',  'Completed',  '2026-04-10', homeowner_id, 'Low',    '2026-04-01'),
        ('C-08-1C', 'Cracked tiles in bathroom',         'Delayed',     None,         homeowner_id, 'Medium', '2026-04-15'),
        ('C-08-1C', 'Faulty electrical socket – hall',   'Pending',     None,         homeowner_id, 'Urgent', '2026-04-28'),
    ]

    # Need a scan for FK
    cur.execute("SELECT id FROM scans ORDER BY id ASC LIMIT 1")
    srow = cur.fetchone()
    if not srow:
        cur.execute("INSERT INTO scans (name) VALUES ('Demo Scan') RETURNING id")
        scan_id = cur.fetchone()[0]
    else:
        scan_id = srow[0]

    inserted = 0
    for unit, desc, status, comp_date, uid, urgency, deadline in sample_defects:
        cur.execute("SELECT id FROM defects WHERE unit=%s AND description=%s LIMIT 1", (unit, desc))
        if cur.fetchone():
            continue
        cur.execute("""
            INSERT INTO defects
                (scan_id, x, y, z, description, status, unit, user_id,
                 urgency, deadline, completed_date,
                 reported_date, severity, priority)
            VALUES (%s,0,0,0,%s,%s,%s,%s,%s,%s,%s,NOW(),'Medium','Medium')
        """, (scan_id, desc, status, unit, uid, urgency, deadline, comp_date))
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {inserted} defect(s). Done!")

if __name__ == '__main__':
    seed()
