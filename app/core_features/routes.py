from flask import render_template
from flask_login import login_required
from . import core_features as bp

@bp.route('/chatbot')
@login_required
def chatbot_ui():
    """Renders the chatbot interface."""
    return render_template('chatbot.html')
