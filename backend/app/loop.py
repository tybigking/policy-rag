"""让 uvicorn 在 Windows 上使用 Selector 事件循环，以兼容 psycopg 异步驱动。"""
import asyncio


def selector_event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
