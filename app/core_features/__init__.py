from flask import Blueprint

core_features = Blueprint('core_features', __name__)

from . import routes
