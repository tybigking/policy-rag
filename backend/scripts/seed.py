import asyncio
import os

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.models import Membership, Organization, User

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:mysecretpassword@localhost:5432/mydb",
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
MEMBER_EMAIL = os.environ.get("MEMBER_EMAIL", "staff@example.com")
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "ChangeMe123!")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    ph = PasswordHasher()

    async with Session() as s:
        org = (await s.execute(select(Organization).limit(1))).scalars().first()
        if org is None:
            org = Organization(name="Acme")
            s.add(org)
            await s.flush()  # 拿到 org.id

        for email, role in [(ADMIN_EMAIL, "admin"), (MEMBER_EMAIL, "member")]:
            user = (await s.execute(select(User).where(User.email == email))).scalars().first()
            if user is None:
                user = User(email=email, password_hash=ph.hash(DEFAULT_PASSWORD))
                s.add(user)
                await s.flush()

            existing = (
                await s.execute(
                    select(Membership).where(
                        Membership.org_id == org.id, Membership.user_id == user.id
                    )
                )
            ).scalars().first()
            if existing is None:
                s.add(Membership(org_id=org.id, user_id=user.id, role=role))

        await s.commit()
        print("seed done:", ADMIN_EMAIL, "admin /", MEMBER_EMAIL, "member")

    await engine.dispose()


if sys.platform == "win32":
    # Windows 默认事件_loop 与 psycopg 异步驱动不兼容，切换为 Selector 事件循环
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if sys.platform == "win32":
    # Windows 默认事件_loop 与 psycopg 异步驱动不兼容，切换为 Selector 事件循环
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    asyncio.run(main())


