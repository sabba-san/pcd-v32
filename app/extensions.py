"""
Flask extensions initialization — all extension instances live here
to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# Redirect to login page when @login_required is triggered
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
