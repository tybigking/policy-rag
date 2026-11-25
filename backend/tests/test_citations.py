
from app.services.citations import parse_citation_labels


def test_parse_labels_removes_out_of_range_and_deduplicates() -> None:
    labels = parse_citation_labels("[S1] 见 [S2]，另有 S9 与 S1。", max_label=3)
    assert labels == [1, 2]


def test_parse_labels_empty_when_none_valid() -> None:
    assert parse_citation_labels("没有引用。", max_label=5) == []
    assert parse_citation_labels("[S9]", max_label=3) == []