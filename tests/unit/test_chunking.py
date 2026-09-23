"""Unit tests for deterministic note chunking."""

import pytest

from app.services.rag.chunking import chunk_text


def _assert_no_content_lost(normalized: str, chunks: list[str]) -> None:
    """
    Assert every whitespace-separated token of `normalized` survives intact
    in at least one chunk.

    Chunks strip() their own leading/trailing whitespace, so the single
    separator space exactly at a non-overlapping chunk boundary is not
    expected to appear in either neighbouring chunk (it carries no content).
    Token-level containment is therefore the meaningful coverage guarantee:
    no word is ever dropped or corrupted by the chunk boundaries.
    """

    for token in normalized.split(" "):
        assert any(token in chunk for chunk in chunks), (
            f"token {token!r} was not found in any chunk"
        )


def test_short_text_produces_single_chunk() -> None:
    result = chunk_text("Recovery guidelines for athletes.")

    assert result == ["Recovery guidelines for athletes."]


def test_long_text_is_split_into_bounded_chunks() -> None:
    text = "word " * 1000

    result = chunk_text(
        text,
        chunk_size=200,
        overlap=40,
    )

    assert len(result) > 1
    assert all(len(chunk) <= 200 for chunk in result)


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("   \n\n   ") == []


def test_invalid_overlap_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="overlap must be smaller than chunk_size",
    ):
        chunk_text(
            "content",
            chunk_size=100,
            overlap=100,
        )


def test_overlap_close_to_chunk_size_terminates_and_is_bounded() -> None:
    text = " ".join(f"word{i}" for i in range(200))
    normalized = " ".join(text.split())

    result = chunk_text(text, chunk_size=20, overlap=19)

    assert len(result) > 1
    assert all(len(chunk) <= 20 for chunk in result)
    _assert_no_content_lost(normalized, result)


def test_text_without_whitespace_terminates_and_is_bounded() -> None:
    """A very long word with no whitespace boundary to cut on."""

    text = "x" * 5000

    result = chunk_text(text, chunk_size=100, overlap=90)

    assert len(result) > 1
    assert all(len(chunk) <= 100 for chunk in result)
    assert "".join(result).replace("x", "") == ""
    assert sum(len(chunk) for chunk in result) >= len(text)


def test_zero_overlap_produces_contiguous_chunks() -> None:
    text = " ".join(f"word{i}" for i in range(100))
    normalized = " ".join(text.split())

    result = chunk_text(text, chunk_size=30, overlap=0)

    assert len(result) > 1
    assert all(len(chunk) <= 30 for chunk in result)
    _assert_no_content_lost(normalized, result)


def test_chunk_size_of_one_terminates_and_covers_every_character() -> None:
    result = chunk_text("abc def", chunk_size=1, overlap=0)

    assert all(len(chunk) <= 1 for chunk in result)
    assert "".join(result) == "abcdef"


def test_single_word_longer_than_chunk_size_is_split_and_bounded() -> None:
    text = "x" * 250

    result = chunk_text(text, chunk_size=100, overlap=20)

    assert len(result) > 1
    assert all(len(chunk) <= 100 for chunk in result)


def test_large_overlap_with_uniform_tokens_has_bounded_chunk_count() -> None:
    """
    Regression test for the exact pathological repro from the chunker bug
    report: `chunk_size=100, overlap=90` over many 30-character tokens.

    Termination alone is not enough: when the whitespace-boundary trim
    shrinks `end` well below what the requested overlap already implies,
    the strict-progress guard degrades into crawling forward one character
    at a time, producing tens of thousands of near-duplicate,
    one-character-shifted chunks (45,931 for this exact input before the
    trim was made overlap-aware). Chunk count must stay in the same order
    of magnitude as the ideal fixed-step count, not blow up.
    """

    text = ("a" * 30 + " ") * 2000
    normalized = " ".join(text.split())

    result = chunk_text(text, chunk_size=100, overlap=90)

    assert len(result) > 1
    assert all(len(chunk) <= 100 for chunk in result)

    ideal_step = 100 - 90
    ideal_chunk_count = len(normalized) // ideal_step

    # Generous multiplier: whitespace trimming makes the real chunk count
    # exceed the ideal fixed-step count, but it must stay within the same
    # order of magnitude. The unfixed implementation produced ~45,900
    # chunks here (~7x this bound); this fails fast against that regression.
    assert len(result) < ideal_chunk_count * 2
