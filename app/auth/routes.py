from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models import User, Defect, Scan

# Import module3 functions for data synchronization
from ..module3.routes import get_defects_for_role, calculate_stats

auth = Blueprint('auth', __name__)


# ── Login / Logout ────────────────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.user_type)

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return _redirect_by_role(user.user_type)

        flash('Invalid email or password. Please try again.', 'error')

    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# ── Role Selection ────────────────────────────────────────────────────────────

@auth.route('/register')
def register():
    return render_template('role/register/selection.html')


# ── Homeowner Registration ────────────────────────────────────────────────────

@auth.route('/register/homeowner', methods=['GET', 'POST'])
def reg_homeowner():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_homeowner'))

        # Support "other_property" when user selects 'Other' in the dropdown
        housing_project = request.form.get('housing_project', '').strip()
        if housing_project.lower() == 'other':
            housing_project = request.form.get('other_property', '').strip()

        user = User(
            user_type              = 'homeowner',
            full_name              = request.form.get('full_name', '').strip(),
            email                  = email,
            housing_project        = housing_project,
            ic_number              = request.form.get('ic_number', '').strip(),
            phone_number           = request.form.get('phone', '').strip(),
            correspondence_address = request.form.get('address', '').strip(),
        )

        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('role/register/reg_homeowner.html')


# ── Lawyer Registration ───────────────────────────────────────────────────────

@auth.route('/register/lawyer', methods=['GET', 'POST'])
def reg_lawyer():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_lawyer'))

        user = User(
            user_type      = 'lawyer',
            full_name      = request.form.get('full_name', '').strip(),
            email          = email,
            law_firm_name  = request.form.get('firm_name', '').strip(),
            bar_council_id = request.form.get('bar_id', '').strip(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('role/register/reg_lawyer.html')


# ── Housing Developer Registration ───────────────────────────────────────────

@auth.route('/register/developer', methods=['GET', 'POST'])
def reg_housedeveloper():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_housedeveloper'))

        company_name = request.form.get('company_name', '').strip()
        if company_name == 'others':
            company_name = request.form.get('other_company_name', '').strip()

        user = User(
            user_type            = 'developer',
            full_name            = request.form.get('full_name', '').strip(),
            email                = email,
            company_name         = company_name,
            ssm_registration     = request.form.get('ssm', '').strip(),
            company_address      = request.form.get('address', '').strip(),
            phone_number         = request.form.get('phone', '').strip(),
            fax_email            = request.form.get('fax_email', '').strip(),
            representative_name  = request.form.get('representative_name', '').strip(),
            representative_nric  = request.form.get('representative_nric', '').strip(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('role/register/reg_housedeveloper.html')


# ── Dashboards ────────────────────────────────────────────────────────────────

@auth.route('/dashboard/homeowner')
@login_required
def homeowner_dashboard():
    """Homeowner dashboard: show the current user's reported defects in Recent Activity."""
    recent_defects = (
        Defect.query
        .filter_by(user_id=current_user.id)
        .order_by(Defect.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template('role/dashboard/homeowner.html', recent_defects=recent_defects)


@auth.route('/dashboard/lawyer')
@login_required
def lawyer_dashboard():
    """Lawyer dashboard: show all defects as the Pending Cases Queue."""
    from sqlalchemy.orm import joinedload
    defects = (
        Defect.query
        .order_by(Defect.created_at.desc())
        .limit(50)
        .all()
    )
    # Collect unique user IDs so we can fetch names in one query
    user_ids = list({d.user_id for d in defects if d.user_id})
    user_map = {u.id: u.full_name for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    pending_cases = []
    for d in defects:
        pending_cases.append({
            'id':            d.id,
            'scan_id':       d.scan_id,
            'scan_name':     d.scan.name if d.scan else None,
            'defect_type':   d.defect_type or 'Unknown',
            'severity':      d.severity or 'Medium',
            'status':        d.status or 'Reported',
            'is_verified':   d.is_verified,
            'client_name':   user_map.get(d.user_id, '—'),
            'assigned_date': d.created_at.strftime('%d %b %Y') if d.created_at else '—',
        })
    return render_template('role/dashboard/lawyer.html', pending_cases=pending_cases)


@auth.route('/dashboard/developer')
@login_required
def developer_dashboard():
    defects = get_defects_for_role("Developer")
    stats = calculate_stats(defects)
    return render_template('role/dashboard/housedeveloper.html', defects=defects, stats=stats)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _redirect_by_role(user_type: str):
    """Redirect to the correct dashboard based on user_type."""
    if user_type == 'developer':
        return redirect(url_for('auth.developer_dashboard'))
    elif user_type == 'lawyer':
        return redirect(url_for('auth.lawyer_dashboard'))
    else:
        return redirect(url_for('auth.homeowner_dashboard'))
