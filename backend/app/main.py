import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, documents, kb, retrieval
from app.config import get_settings

if sys.platform == "win32":
    # Windows 默认 Proactor 事件循环不支持 psycopg 异步驱动的 add_reader，切换为 Selector
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(
    title="PolicyRAG API",
    description="PolicyRAG 制度文档问答系统后端",
    version="0.7.0",
)

settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router)
app.include_router(kb.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(retrieval.router)


@app.get("/health")
async def health() -> dict:
    """健康检查接口。"""
    return {"status": "ok"}


# 阶段 7：前端静态资源。挂载在最后，避免吞掉 API 路由。
backend_root = Path(__file__).resolve().parent.parent
frontend_dir = Path(settings.frontend_dir)
if not frontend_dir.is_absolute():
    frontend_dir = (backend_root / frontend_dir).resolve()
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")