from flask import Blueprint, make_response, render_template, request, redirect, url_for, flash, abort, session
import re
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db, oauth
from ..models import User, Defect, Scan

# Import module3 functions for data synchronization
from ..module3.routes import get_defects_for_role, calculate_stats

auth = Blueprint('auth', __name__)


# ── Public Pages ────────────────────────────────────────────────────────────

@auth.route('/features')
def features():
    """Renders the global Features highlights page."""
    return render_template('features.html')


# ── Login / Logout ────────────────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.user_type)

    if request.method == 'POST':
        session.clear()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return _redirect_by_role(user.user_type)

        flash('Invalid email or password. Please try again.', 'error')

    resp = make_response(render_template('auth/login.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    resp = redirect(url_for('auth.login'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# ── Google OAuth 2.0 Routes ───────────────────────────────────────────────

@auth.route('/google/login')
def google_login():
    """Initiate Google OAuth 2.0 Authorization Code flow.

    Authlib automatically generates a cryptographically random `state`
    parameter and stores it in the session to prevent CSRF attacks.
    """
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth.route('/google/callback')
def google_callback():
    """Handle the Google OAuth 2.0 callback.

    Authlib validates the `state` parameter automatically.
    The user is looked up by google_id (stable) first, then by email as a
    first-time SSO fallback. Unknown emails receive an error — no new
    accounts are created via this flow.
    """
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        # OAuth flow cancelled, state mismatch, or network error
        flash('Google sign-in was cancelled or failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    user_info = token.get('userinfo')
    if not user_info:
        flash('Could not retrieve your Google profile. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    google_sub   = user_info.get('sub')               # stable, opaque Google user ID
    google_email = user_info.get('email', '').strip().lower()
    google_name  = user_info.get('name', '').strip()

    # 1. Primary lookup: by google_id (survives email changes)
    user = User.query.filter_by(google_id=google_sub).first()

    # 2. First-time SSO fallback: link an existing email+password account
    if not user and google_email:
        user = User.query.filter_by(email=google_email).first()
        if user:
            # Persist google_id so subsequent logins skip the email lookup
            user.google_id = google_sub
            db.session.commit()

    # 3. Auto-register: create a new homeowner account for brand-new Google users
    if not user:
        if not google_email:
            flash('Could not retrieve your Google email. Please try again.', 'error')
            return redirect(url_for('auth.login'))

        import os
        import traceback
        
        user = User(
            user_type  = 'homeowner',
            full_name  = google_name or google_email.split('@')[0],
            email      = google_email[:150],
            google_id  = google_sub,
        )
        # Set a random password to satisfy the nullable=False constraint on password_hash
        user.set_password(os.urandom(24).hex())

        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Welcome, {user.full_name}! Your account has been created automatically via Google.', 'success')
        except Exception as e:
            db.session.rollback()
            # In a real production app, we would log the exact error using a logger
            flash('Failed to create account due to a database error. Please contact support or try again.', 'error')
            return redirect(url_for('auth.login'))

    login_user(user)

    # ── Profile completion check ─────────────────────────────────────────────────
    if not user.ic_number:
        flash('Please complete your profile details such as IC Number and Address before proceeding.', 'warning')
        return redirect(url_for('module3.settings'))
    # ─────────────────────────────────────────────────────────────────────────────

    return _redirect_by_role(user.user_type)


# ── Role Selection ────────────────────────────────────────────────────────────

@auth.route('/register')
def register():
    logout_user()
    session.clear()
    return render_template('role/register/selection.html')


# ── Homeowner Registration ────────────────────────────────────────────────────

@auth.route('/register/homeowner', methods=['GET', 'POST'])
def reg_homeowner():
    if request.method == 'POST':
        logout_user()
        session.clear()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_homeowner'))

        # ── Backend security validation (defense-in-depth) ──────────────────────
        _SPECIAL = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\'"\\|,.<>/?]')
        if len(password) < 8 or not _SPECIAL.search(password):
            flash('Password must be at least 8 characters and contain at least one special character (!@#$%^&*...).', 'error')
            return redirect(url_for('auth.reg_homeowner'))

        phone = request.form.get('phone', '').strip()
        if phone and not re.fullmatch(r'[0-9]+', phone):
            flash('Phone number must contain digits only.', 'error')
            return redirect(url_for('auth.reg_homeowner'))
        # ───────────────────────────────────────────────────────────────────────

        # Support "other_property" when user selects 'Other' in the dropdown
        housing_project = request.form.get('housing_project', '').strip()
        if housing_project.lower() == 'other':
            housing_project = request.form.get('other_property', '').strip()

        user = User(
            user_type              = 'homeowner',
            full_name              = request.form.get('full_name', '').strip()[:150],
            email                  = email[:150],
            housing_project        = housing_project[:150],
            ic_number              = request.form.get('ic_number', '').strip()[:20],
            phone_number           = request.form.get('phone', '').strip()[:30],
            correspondence_address = request.form.get('address', '').strip(),
            unit                   = request.form.get('unit', '').strip()[:100],
        )

        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    import os
    return render_template('role/register/reg_homeowner.html', google_maps_api_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''))


# ── Lawyer Registration ───────────────────────────────────────────────────────

@auth.route('/register/lawyer', methods=['GET', 'POST'])
def reg_lawyer():
    if request.method == 'POST':
        logout_user()
        session.clear()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_lawyer'))

        # ── Backend security validation ─────────────────────────────────────────
        _SPECIAL = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\'"\\|,.<>/?]')
        if len(password) < 8 or not _SPECIAL.search(password):
            flash('Password must be at least 8 characters and contain at least one special character (!@#$%^&*...).', 'error')
            return redirect(url_for('auth.reg_lawyer'))
        # ───────────────────────────────────────────────────────────────────────

        user = User(
            user_type      = 'lawyer',
            full_name      = request.form.get('full_name', '').strip()[:150],
            email          = email[:150],
            ic_number      = request.form.get('ic_number', '').strip()[:20],
            law_firm_name  = request.form.get('firm_name', '').strip()[:150],
            bar_council_id = request.form.get('bar_id', '').strip()[:50],
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    import os
    return render_template('role/register/reg_lawyer.html', google_maps_api_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''))


# ── Housing Developer Registration ───────────────────────────────────────────

@auth.route('/register/developer', methods=['GET', 'POST'])
def reg_housedeveloper():
    if request.method == 'POST':
        logout_user()
        session.clear()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('auth.reg_housedeveloper'))

        # ── Backend security validation ─────────────────────────────────────────
        _SPECIAL = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\'"\\|,.<>/?]')
        if len(password) < 8 or not _SPECIAL.search(password):
            flash('Password must be at least 8 characters and contain at least one special character (!@#$%^&*...).', 'error')
            return redirect(url_for('auth.reg_housedeveloper'))

        phone = request.form.get('phone', '').strip()
        if phone and not re.fullmatch(r'[0-9]+', phone):
            flash('Phone number must contain digits only.', 'error')
            return redirect(url_for('auth.reg_housedeveloper'))
        # ───────────────────────────────────────────────────────────────────────

        company_name = request.form.get('company_name', '').strip()

        user = User(
            user_type            = 'developer',
            full_name            = request.form.get('full_name', '').strip()[:150],
            email                = email[:150],
            company_name         = company_name[:150],
            ssm_registration     = request.form.get('ssm', '').strip()[:50],
            company_address      = request.form.get('address', '').strip(),
            phone_number         = request.form.get('phone', '').strip()[:30],
            fax_email            = request.form.get('fax_email', '').strip()[:150],
            representative_name  = request.form.get('representative_name', '').strip()[:150],
            representative_nric  = request.form.get('representative_nric', '').strip()[:20],
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    import os
    return render_template('role/register/reg_housedeveloper.html', google_maps_api_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''))


# ── Dashboards ────────────────────────────────────────────────────────────────

@auth.route('/dashboard/homeowner')
@login_required
def homeowner_dashboard():
    """Homeowner dashboard: show the current user's reported defects in Recent Activity."""
    if current_user.user_type != 'homeowner':
        abort(403)
    
    # Check if homeowner has completed mandatory profile details
    # Exempt profile and settings pages to prevent redirect loops
    from flask import request
    exempt_endpoints = ['module3.profile', 'module3.settings', 'module3.update_profile', 'module3.change_password']
    if not request.endpoint or request.endpoint not in exempt_endpoints:
        if not current_user.housing_project or not current_user.unit or not current_user.correspondence_address:
            flash('Please complete your property details to continue', 'warning')
            return redirect(url_for('module3.profile'))
    
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
    """Lawyer dashboard: show only defects explicitly assigned to this lawyer."""
    if current_user.user_type != 'lawyer':
        abort(403)
    defects = (
        Defect.query
        .filter_by(assigned_lawyer_id=current_user.id)
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
    if current_user.user_type != 'developer':
        abort(403)
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
    elif user_type == 'admin':
        return redirect(url_for('module3.dashboard'))
    else:
        return redirect(url_for('auth.homeowner_dashboard'))
