from app.core.extensions import db


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    server_id = db.Column(db.Integer, nullable=False, index=True)
    description = db.Column(db.String(255))
    # 可扩展：icon、排序等


class Channel(db.Model):
    __tablename__ = "channels"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    server_id = db.Column(db.Integer, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    type = db.Column(
        db.Enum("text", "voice", "video", "announcement", name="channel_type"),
        nullable=False,
        default="text",
    )
    description = db.Column(db.String(255))
    icon = db.Column(db.String(255))
    # 关系
    category = db.relationship("Category", backref=db.backref("channels", lazy=True))


class ChannelMember(db.Model):
    __tablename__ = "channel_members"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, nullable=False, index=True)
    joined_at = db.Column(db.DateTime, server_default=db.func.now())
    role = db.Column(
        db.Enum("member", "admin", name="channel_member_role"),
        nullable=False,
        default="member",
    )
    is_muted = db.Column(db.Boolean, nullable=False, default=False)
    # 可扩展：频道内角色、状态、禁言等
    __table_args__ = (
        db.UniqueConstraint("channel_id", "user_id", name="uix_channel_user"),
    )


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, nullable=False, index=True)
    type = db.Column(
        db.Enum("text", "image", "file", name="message_type"),
        nullable=False,
        default="text",
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )
    is_edited = db.Column(db.Boolean, nullable=False, default=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    mentions = db.Column(db.JSON, nullable=True)  # 存储被@的用户ID列表
    reply_to_id = db.Column(
        db.Integer, db.ForeignKey("messages.id"), nullable=True, index=True
    )  # 回复的消息ID
    # 转发相关字段
    is_forwarded = db.Column(
        db.Boolean, nullable=False, default=False
    )  # 是否为转发消息
    original_message_id = db.Column(
        db.Integer, db.ForeignKey("messages.id"), nullable=True, index=True
    )  # 原消息ID
    original_channel_id = db.Column(db.Integer, nullable=True)  # 原频道ID
    original_user_id = db.Column(db.Integer, nullable=True)  # 原发送者ID
    forward_comment = db.Column(db.String(255), nullable=True)  # 转发时的评论
    # 置顶相关字段
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)  # 是否为置顶消息
    pinned_at = db.Column(db.DateTime, nullable=True)  # 置顶时间
    pinned_by = db.Column(db.Integer, nullable=True)  # 置顶操作者ID
    # 可扩展：引用消息、消息状态、撤回等

    # 关系
    channel = db.relationship("Channel", backref=db.backref("messages", lazy=True))


class SearchHistory(db.Model):
    __tablename__ = "search_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    query = db.Column(db.String(255), nullable=False)  # 搜索关键词
    search_type = db.Column(
        db.Enum("channel", "global", name="search_type"), nullable=False
    )  # 搜索类型
    channel_id = db.Column(
        db.Integer, nullable=True, index=True
    )  # 频道内搜索时的频道ID
    filters = db.Column(db.JSON, nullable=True)  # 搜索过滤条件（用户、时间范围等）
    result_count = db.Column(db.Integer, nullable=False, default=0)  # 搜索结果数量
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    # 可扩展：搜索频率统计、热门搜索等


class MessageReaction(db.Model):
    __tablename__ = "message_reactions"
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("messages.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, nullable=False, index=True)
    reaction = db.Column(db.String(10), nullable=False)  # 表情符号，如 👍, ❤️, 😂
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 唯一约束：同一用户对同一消息的同一表情只能有一个
    __table_args__ = (
        db.UniqueConstraint(
            "message_id", "user_id", "reaction", name="uix_message_user_reaction"
        ),
    )

    # 关系
    message = db.relationship("Message", backref=db.backref("reactions", lazy=True))
