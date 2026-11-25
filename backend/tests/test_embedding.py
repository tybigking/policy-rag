import asyncio

import pytest

from app.services.embedding import EmbeddingError, MockEmbeddingProvider, embed_texts


class _WrongDimProvider:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_mock_embedding_is_deterministic_and_normalized() -> None:
    provider = MockEmbeddingProvider(dim=8)
    first = asyncio.run(provider.embed(["年假制度"]))
    second = asyncio.run(provider.embed(["年假制度"]))
    assert first == second
    assert len(first[0]) == 8
    import math

    norm = math.sqrt(sum(v * v for v in first[0]))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_embed_texts_batches_and_validates_dimension() -> None:
    provider = MockEmbeddingProvider(dim=5)
    vectors = asyncio.run(embed_texts(["a", "b", "c"], provider=provider))
    assert len(vectors) == 3
    assert all(len(v) == 5 for v in vectors)

    with pytest.raises(EmbeddingError):
        asyncio.run(embed_texts(["a", "b"], provider=_WrongDimProvider()))