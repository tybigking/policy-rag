"""创建演示用户，供本地联调。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe -m app.seed
"""
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User

DEMO_USERNAME = "alice"
DEMO_PASSWORD = "secret123"


def seed() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == DEMO_USERNAME).first()
        if existing is not None:
            print(f"演示用户已存在：{DEMO_USERNAME}，跳过创建")
            return
        user = User(
            username=DEMO_USERNAME,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.commit()
        print(f"已创建演示用户：{DEMO_USERNAME} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
