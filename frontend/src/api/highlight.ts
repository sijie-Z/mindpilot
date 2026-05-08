/**
 * Semantic highlighting API.
 * Provides sentence-level relevance scoring for precise search highlighting.
 */
import api from './index'

export interface SentenceScore {
  sentence: string
  score: number
  start: number
  end: number
}

export interface HighlightResponse {
  query: string
  sentences: SentenceScore[]
  top_sentences: string[]
}

export interface HighlightedChunk {
  chunk_id: string
  content: string
  highlighted_sentences: string[]
  sentence_scores: Array<{ sentence: string; score: number }>
  [key: string]: unknown
}

export const highlightApi = {
  /**
   * Get sentence-level relevance scores for a text.
   */
  async highlightSentences(
    query: string,
    text: string,
    topK: number = 5
  ): Promise<HighlightResponse> {
    const response = await api.post('/highlight/sentences', {
      query,
      text,
      top_k: topK,
    })
    return response.data
  },

  /**
   * Highlight relevant sentences within multiple chunks.
   */
  async highlightChunks(
    query: string,
    chunks: Array<{ chunk_id: string; content: string; [key: string]: unknown }>,
    topK: number = 3
  ): Promise<HighlightedChunk[]> {
    const response = await api.post('/highlight/chunks', null, {
      params: { query, top_k: topK },
      data: chunks,
    })
    return response.data.chunks
  },
}

export default highlightApi
