from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from . import core_features as bp

@bp.route('/guide')
@login_required
def guide():
    """Renders the role-based user guide."""
    return render_template('help_guide.html')

@bp.route('/get-started')
@login_required
def get_started():
    """Renders the Get Started & FAQ page."""
    return render_template('get_started_faq.html')

@bp.route('/chatbot')
@login_required
def chatbot_ui():
    """Renders the chatbot interface with auto-fill data for the Notice Letter form."""
    from ..models import User

    # Fetch the assigned developer so Jinja can pre-fill Sections B & C
    linked_developer = None
    if current_user.assigned_developer_id:
        linked_developer = User.query.get(current_user.assigned_developer_id)

    return render_template('chatbot.html', linked_developer=linked_developer)

