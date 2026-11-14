import asyncio
import sys

from fastapi import FastAPI

from app.api import auth

if sys.platform == "win32":
    # Windows 默认 Proactor 事件循环不支持 psycopg 异步驱动的 add_reader，切换为 Selector
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(
    title="PolicyRAG API",
    description="PolicyRAG 制度文档问答系统后端",
    version="0.1.0",
)

app.include_router(auth.router)


@app.get("/health")
async def health() -> dict:
    """健康检查接口。"""
    return {"status": "ok"}
