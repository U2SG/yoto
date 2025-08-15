from datetime import datetime
from app.core.extensions import db


class BaseModel(db.Model):
    __abstract__ = True
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
