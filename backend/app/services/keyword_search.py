"""阶段 4：中文关键词检索（BM25）。

使用 jieba 做中文分词，在全量候选 chunk 上按 BM25 打分。
第一版候选池为授权知识库内的全部分块；规模更大时可换成 PostgreSQL FTS 或引入倒排表。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import jieba

_TOKEN = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """中文用 jieba，英文和数字按词元保留。"""
    tokens: list[str] = []
    for part in _TOKEN.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            tokens.extend(w for w in jieba.lcut(part) if w.strip())
        elif part.strip():
            tokens.append(part)
    return tokens


@dataclass(frozen=True)
class KeywordHit:
    chunk_id: object
    score: float


class BM25Index:
    """轻量 BM25：一次性拿到语料后构建统计，再做查询打分。"""

    def __init__(self, docs: list[tuple[object, str]]) -> None:
        self.docs = docs
        self.doc_tokens = [tokenize(text) for _, text in docs]
        self.doc_count = len(self.doc_tokens)
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        total = sum(self.doc_lengths)
        self.avgdl = total / self.doc_count if self.doc_count else 0.0
        self.df: dict[str, int] = {}
        for tokens in self.doc_tokens:
            for token in set(tokens):
                self.df[token] = self.df.get(token, 0) + 1

    def score(self, query: str, *, top_k: int = 10) -> list[KeywordHit]:
        query_tokens = tokenize(query)
        hits: list[KeywordHit] = []
        k1 = 1.5
        b = 0.75

        for index, tokens in enumerate(self.doc_tokens):
            tf: dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            doc_len = len(tokens)
            score = 0.0
            for token in query_tokens:
                f = tf.get(token, 0)
                if f == 0:
                    continue
                df = self.df.get(token, 0)
                idf = math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))
                denom = f + k1 * (1 - b + b * doc_len / self.avgdl)
                score += idf * (f * (k1 + 1)) / denom
            if score > 0:
                doc_id, _ = self.docs[index]
                hits.append(KeywordHit(chunk_id=doc_id, score=score))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]