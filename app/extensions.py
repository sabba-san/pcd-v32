"""
Flask extensions initialization — all extension instances live here
to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
login_manager = LoginManager()
oauth = OAuth()

# Redirect to login page when @login_required is triggered
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
