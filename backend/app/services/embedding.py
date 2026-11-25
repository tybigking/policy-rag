"""阶段 3：Embedding 服务。

- provider=mock：离线确定性向量（仅用于开发与测试，无语义效果）。
- provider=openai：OpenAI 兼容的 /embeddings 接口。
两种 provider 输出的维度都必须等于配置的 embedding_dim，写入前再次校验。
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.config import get_settings


class EmbeddingError(Exception):
    """向量生成失败，调用方应把任务置为可重试的失败。"""


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return [0.0] * len(vector)
    return [v / norm for v in vector]


def _validate_dim(vectors: list[list[float]], expected: int) -> None:
    for vector in vectors:
        if len(vector) != expected:
            raise EmbeddingError(
                f"向量维度不一致：模型返回 {len(vector)}，配置期望 {expected}"
            )


class MockEmbeddingProvider:
    """确定性 mock：对同一文本总是返回相同向量，保证回填可重复验证。"""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(_mock_vector(text, self.dim))
        return vectors


def _mock_vector(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vector = [((digest[i % len(digest)] + i * 31) % 256) / 255.0 for i in range(dim)]
    return _normalize_vector(vector)


class OpenAIEmbeddingProvider:
    """OpenAI 兼容 embedding 客户端；配置全部来自环境变量。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dim: int,
        timeout_seconds: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingError("EMBEDDING_API_KEY 未配置，无法调用向量模型")
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "input": texts}
        # text-embedding-3 系列支持指定维度；其他模型忽略。
        payload["dimensions"] = self.dim

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingError("向量模型请求超时") from exc
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(f"向量模型返回错误：{exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise EmbeddingError(f"向量模型网络错误：{exc}") from exc

        items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        vectors = [item["embedding"] for item in items]
        _validate_dim(vectors, self.dim)
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider(dim=settings.embedding_dim)
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    raise EmbeddingError(f"不支持的 EMBEDDING_PROVIDER：{settings.embedding_provider}")


async def embed_texts(
    texts: list[str], *, provider: EmbeddingProvider | None = None
) -> list[list[float]]:
    """批量生成向量：分批调用，单批失败重试一次后整体失败。"""
    settings = get_settings()
    provider = provider or get_embedding_provider()
    if not texts:
        return []

    batch_size = max(settings.embedding_batch_size, 1)
    out: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            out.extend(await provider.embed(batch))
        except EmbeddingError:
            # 简单重试一次；再次失败则把整批标记为失败，不做半成功状态
            out.extend(await provider.embed(batch))

    expected_dim = getattr(provider, 'dim', settings.embedding_dim)
    _validate_dim(out, expected_dim)
    return out