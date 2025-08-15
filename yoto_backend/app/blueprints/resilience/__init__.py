from flask import Blueprint

resilience_bp = Blueprint("resilience", __name__, url_prefix="/api/resilience")

from . import views
