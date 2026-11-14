from fastapi import FastAPI

from app.api import auth

app = FastAPI(
    title="FastAPI Auth API",
    description="用户注册、登录与 JWT 鉴权 API",
    version="0.1.0",
)

app.include_router(auth.router)


@app.get("/")
def root() -> dict:
    """服务根路径，用于快速确认应用已启动。"""
    return {"message": "FastAPI auth API is running"}


@app.get("/health")
def health() -> dict:
    """健康检查接口，部署和联调时常用。"""
    return {"status": "ok"}
