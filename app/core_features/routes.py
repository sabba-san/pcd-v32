from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from . import core_features as bp

@bp.route('/guide')
@login_required
def guide():
    """Renders the role-based user guide."""
    return render_template('help_guide.html')

@bp.route('/chatbot')
@login_required
def chatbot_ui():
    """Renders the chatbot interface."""
    return render_template('chatbot.html')
