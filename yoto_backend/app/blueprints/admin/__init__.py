from flask import Blueprint

admin_bp = Blueprint("admin", __name__)
audit_bp = Blueprint("audit", __name__)

from . import views
from . import audit_views
