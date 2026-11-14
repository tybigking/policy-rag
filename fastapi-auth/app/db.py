from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False}
    if get_settings().database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖：每个请求一个数据库会话，用完关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
