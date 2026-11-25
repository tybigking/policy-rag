"""阶段 6：模型适配器（只支持一个供应商：OpenAI 兼容的 /chat/completions）。"""
from __future__ import annotations

import httpx

from app.config import get_settings


class ModelError(Exception):
    """模型调用失败；调用方决定重试、降级或把消息置为 failed。"""

    def __init__(self, message: str, *, kind: str = "model_error") -> None:
        super().__init__(message)
        self.kind = kind


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
) -> tuple[str, dict | None]:
    """调用一次模型返回文本与 token 用量。失败抛 ModelError。"""
    settings = get_settings()
    if not settings.llm_api_key:
        raise ModelError("LLM_API_KEY 未配置", kind="misconfigured")

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        raise ModelError("模型请求超时", kind="timeout") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (429, 402):
            raise ModelError("模型限流或额度不足", kind="rate_limited") from exc
        raise ModelError(f"模型返回错误：{status}", kind="http_error") from exc
    except httpx.RequestError as exc:
        raise ModelError(f"模型网络错误：{exc}", kind="network_error") from exc

    choices = data.get("choices") or []
    if not choices:
        raise ModelError("模型返回为空", kind="empty_output")

    content = (choices[0].get("message") or {}).get("content") or ""
    if not content.strip():
        raise ModelError("模型返回为空", kind="empty_output")

    usage = data.get("usage")
    return content, usage