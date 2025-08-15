from app.models.base import BaseModel
from app.core.extensions import db


class User(BaseModel):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(180), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
