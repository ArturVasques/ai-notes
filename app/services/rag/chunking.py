"""
Text chunking for document ingestion.

Documents are divided into overlapping chunks before embeddings are created.
Overlap helps preserve context around chunk boundaries.

Used by:
- document ingestion service before embedding generation.

A production system may later replace this implementation with
token-aware or document-format-aware chunking without affecting repositories
or agents.
"""


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[str]:
    """Split text into bounded overlapping chunks."""

    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    if overlap < 0:
        raise ValueError("overlap must not be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    normalized = " ".join(text.split())
    length = len(normalized)

    if not normalized:
        return []

    chunks: list[str] = []
    start = 0

    while start < length:
        end = min(start + chunk_size, length)

        # Avoid cutting a word when a nearby whitespace boundary exists.
        # Only trim to that boundary when doing so still leaves room for the
        # requested overlap: otherwise the trim itself would shrink `end` far
        # enough that the next step degrades to crawling forward one
        # character at a time (see the strict-progress guard below), turning
        # a large-overlap configuration into tens of thousands of
        # near-duplicate, one-character-shifted chunks.
        if end < length:
            last_space = normalized.rfind(" ", start, end)

            if last_space > start + chunk_size // 2 and last_space > start + overlap:
                end = last_space

        stripped = normalized[start:end].strip()

        if stripped:
            chunks.append(stripped)

        if end >= length:
            break

        # `start` must strictly increase every iteration. A short chunk
        # (whitespace trimming, or overlap close to chunk_size) must never
        # leave `start` unchanged or push it backwards, or the loop would
        # never terminate.
        start = max(end - overlap, start + 1)

    return chunks
