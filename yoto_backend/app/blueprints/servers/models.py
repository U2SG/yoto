from app.core.extensions import db


class Server(db.Model):
    __tablename__ = "servers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    owner_id = db.Column(db.Integer, nullable=False)


class ServerMember(db.Model):
    __tablename__ = "server_members"
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("server_id", "user_id", name="uq_server_user"),
    )
