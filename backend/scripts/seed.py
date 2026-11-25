import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    KnowledgeBase,
    KnowledgeBasePermission,
    Membership,
    Organization,
    User,
)

DATABASE_URL = get_settings().database_url
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
MEMBER_EMAIL = os.environ.get("MEMBER_EMAIL", "staff@example.com")
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "ChangeMe123!")

# 阶段 5 种子：管理员可读全部；员工只读「全员须知」和显式授权的「报销制度」，
# 无法看到「薪酬保密」。
DEMO_KBS = [
    {"name": "全员须知", "visibility": "org"},
    {"name": "报销制度", "visibility": "restricted"},
    {"name": "薪酬保密", "visibility": "restricted"},
]
MEMBER_GRANTED_KB = "报销制度"


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        org = (await s.execute(select(Organization).limit(1))).scalars().first()
        if org is None:
            org = Organization(name="Acme")
            s.add(org)
            await s.flush()

        users: dict[str, User] = {}
        for email, role in [(ADMIN_EMAIL, "admin"), (MEMBER_EMAIL, "member")]:
            user = (
                await s.execute(select(User).where(User.email == email))
            ).scalars().first()
            if user is None:
                user = User(email=email, password_hash=hash_password(DEFAULT_PASSWORD))
                s.add(user)
                await s.flush()
            users[role] = user

            membership = (
                await s.execute(
                    select(Membership).where(
                        Membership.org_id == org.id,
                        Membership.user_id == user.id,
                    )
                )
            ).scalars().first()
            if membership is None:
                s.add(Membership(org_id=org.id, user_id=user.id, role=role))

        kbs: dict[str, KnowledgeBase] = {}
        for spec in DEMO_KBS:
            kb = (
                await s.execute(
                    select(KnowledgeBase).where(
                        KnowledgeBase.org_id == org.id,
                        KnowledgeBase.name == spec["name"],
                    )
                )
            ).scalars().first()
            if kb is None:
                kb = KnowledgeBase(
                    org_id=org.id,
                    name=spec["name"],
                    visibility=spec["visibility"],
                )
                s.add(kb)
                await s.flush()
            kbs[spec["name"]] = kb

        granted_kb = kbs[MEMBER_GRANTED_KB]
        grant = (
            await s.execute(
                select(KnowledgeBasePermission).where(
                    KnowledgeBasePermission.kb_id == granted_kb.id,
                    KnowledgeBasePermission.user_id == users["member"].id,
                )
            )
        ).scalars().first()
        if grant is None:
            s.add(
                KnowledgeBasePermission(
                    kb_id=granted_kb.id,
                    user_id=users["member"].id,
                    access_level="read",
                )
            )

        await s.commit()
        print("seed done:")
        print(f"  admin : {ADMIN_EMAIL} / {DEFAULT_PASSWORD}")
        print(f"  member: {MEMBER_EMAIL} / {DEFAULT_PASSWORD}")
        print(f"  kbs   : {', '.join(kbs.keys())}")
        print(f"  member granted: {MEMBER_GRANTED_KB}")

    await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())