"""
Pydantic 序列化模型定义入口。
后续在此文件中定义各业务模块的 Pydantic BaseModel 子类。
"""

from pydantic import BaseModel


class UserSchema(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class ServerSchema(BaseModel):
    id: int
    name: str
    owner_id: int

    class Config:
        from_attributes = True


class RoleSchema(BaseModel):
    id: int
    name: str
    server_id: int

    class Config:
        from_attributes = True
