"""
Semantic highlighting API.

Provides sentence-level relevance scoring for search results,
enabling precise highlighting of matching content.
"""
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logger import get_logger
from app.rag.embedder import embedder

logger = get_logger(__name__)
router = APIRouter()


class HighlightRequest(BaseModel):
    """Request for semantic highlighting."""
    query: str
    text: str
    top_k: int = 5


class SentenceScore(BaseModel):
    """Sentence with relevance score."""
    sentence: str
    score: float
    start: int
    end: int


class HighlightResponse(BaseModel):
    """Response with highlighted sentences."""
    query: str
    sentences: list[SentenceScore]
    top_sentences: list[str]


class HighlightChunksRequest(BaseModel):
    """Request for chunk highlighting."""
    chunks: list[dict[str, Any]]
    query: str
    top_k: int = 3


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """
    Split text into sentences with position tracking.
    Supports Chinese and English sentence boundaries.
    """
    # Pattern matches sentence endings: . ! ? 。！？ followed by whitespace or end
    pattern = r'[^.!?。！？\n]+[.!?。！？\n]*'
    matches = list(re.finditer(pattern, text, re.MULTILINE))

    sentences = []
    for match in matches:
        sentence = match.group().strip()
        if sentence and len(sentence) > 5:  # Skip very short fragments
            sentences.append((sentence, match.start(), match.end()))

    return sentences


async def compute_sentence_scores(
    query: str,
    sentences: list[tuple[str, int, int]],
) -> list[dict[str, Any]]:
    """
    Compute relevance scores for each sentence against the query.

    Uses embedding similarity for semantic relevance.
    """
    if not sentences:
        return []

    try:
        # Get query embedding
        query_embedding = await embedder.embed_query(query)

        # Get sentence embeddings
        sentence_texts = [s[0] for s in sentences]
        sentence_embeddings = await embedder.embed_documents(sentence_texts)

        # Compute cosine similarities
        import numpy as np

        query_vec = np.array(query_embedding)
        scores = []

        for i, sent_emb in enumerate(sentence_embeddings):
            sent_vec = np.array(sent_emb)
            # Cosine similarity
            similarity = np.dot(query_vec, sent_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(sent_vec) + 1e-8
            )
            scores.append({
                "sentence": sentences[i][0],
                "score": float(similarity),
                "start": sentences[i][1],
                "end": sentences[i][2],
            })

        # Sort by score descending
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores

    except Exception as e:
        logger.warning("Sentence scoring failed, using fallback", error=str(e))
        # Fallback: keyword matching scores
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        scores = []
        for sentence, start, end in sentences:
            sent_lower = sentence.lower()
            # Count keyword matches
            word_matches = sum(1 for w in query_words if w in sent_lower)
            # Exact phrase match bonus
            phrase_bonus = 0.5 if query_lower in sent_lower else 0
            score = min(1.0, (word_matches / max(len(query_words), 1)) + phrase_bonus)

            scores.append({
                "sentence": sentence,
                "score": score,
                "start": start,
                "end": end,
            })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores


@router.post("/sentences")
async def highlight_sentences(request: HighlightRequest):
    """
    Get sentence-level relevance scores for semantic highlighting.

    Returns sentences sorted by relevance, with position information
    for precise highlighting in the frontend.
    """
    if not request.text.strip():
        return HighlightResponse(
            query=request.query,
            sentences=[],
            top_sentences=[],
        )

    # Split into sentences
    sentences = split_sentences(request.text)

    if not sentences:
        return HighlightResponse(
            query=request.query,
            sentences=[],
            top_sentences=[],
        )

    # Compute scores
    scored_sentences = await compute_sentence_scores(request.query, sentences)

    # Return top-k sentences
    top_k = min(request.top_k, len(scored_sentences))
    top_sentences = [s["sentence"] for s in scored_sentences[:top_k]]

    return HighlightResponse(
        query=request.query,
        sentences=[
            SentenceScore(
                sentence=s["sentence"],
                score=s["score"],
                start=s["start"],
                end=s["end"],
            )
            for s in scored_sentences
        ],
        top_sentences=top_sentences,
    )


@router.post("/chunks")
async def highlight_chunks(request: HighlightChunksRequest):
    """
    Highlight relevant sentences within multiple chunks.

    Returns chunks with highlighted sentences marked.
    """
    results = []

    for chunk in request.chunks:
        content = chunk.get("content", "")
        if not content:
            results.append(chunk)
            continue

        # Split and score
        sentences = split_sentences(content)
        scored = await compute_sentence_scores(request.query, sentences)

        # Get top sentences for this chunk
        top_sentences = [s["sentence"] for s in scored[:request.top_k]]

        # Add highlight info to chunk
        highlighted_chunk = {
            **chunk,
            "highlighted_sentences": top_sentences,
            "sentence_scores": [
                {"sentence": s["sentence"], "score": s["score"]}
                for s in scored[:request.top_k]
            ],
        }
        results.append(highlighted_chunk)

    return {"chunks": results}
