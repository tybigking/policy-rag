"""阶段 6：引用解析与校验。

模型输出里的 S1、[S1] 只是候选编号，必须由程序清洗、去重、映射到真实候选分块；
不存在的编号一律删除，没有有效引用时严格模式拒答。
"""
from __future__ import annotations

import re

_LABEL = re.compile(r"\[?S(\d{1,2})\]?", re.IGNORECASE)


def parse_citation_labels(text: str, *, max_label: int) -> list[int]:
    """提取回答中出现的 S 编号，按出现顺序去重，并过滤越界编号。"""
    found: list[int] = []
    seen: set[int] = set()
    for match in _LABEL.finditer(text):
        number = int(match.group(1))
        if 1 <= number <= max_label and number not in seen:
            seen.add(number)
            found.append(number)
    return found