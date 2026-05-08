<template>
  <div class="highlighted-text" v-html="highlightedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface SentenceScore {
  sentence: string
  score: number
  start: number
  end: number
}

const props = defineProps<{
  text: string
  sentences?: SentenceScore[]
  topSentences?: string[]
  threshold?: number
}>()

const highlightedHtml = computed(() => {
  if (!props.text) return ''

  // If we have sentence scores, use them for precise highlighting
  if (props.sentences && props.sentences.length > 0) {
    return highlightByScores(props.text, props.sentences, props.threshold || 0.5)
  }

  // If we have top sentences, highlight them directly
  if (props.topSentences && props.topSentences.length > 0) {
    return highlightBySentences(props.text, props.topSentences)
  }

  // No highlighting
  return escapeHtml(props.text)
})

function highlightByScores(
  text: string,
  sentences: SentenceScore[],
  threshold: number
): string {
  // Sort by position to process in order
  const sorted = [...sentences]
    .filter(s => s.score >= threshold)
    .sort((a, b) => a.start - b.start)

  if (sorted.length === 0) return escapeHtml(text)

  let result = ''
  let lastEnd = 0

  for (const sentence of sorted) {
    // Add text before this sentence
    if (sentence.start > lastEnd) {
      result += escapeHtml(text.slice(lastEnd, sentence.start))
    }

    // Add highlighted sentence
    const intensity = Math.min(1, sentence.score)
    const bgColor = `rgba(250, 204, 21, ${intensity * 0.4})` // Yellow highlight
    result += `<mark class="semantic-highlight" style="background: ${bgColor}" title="相关度: ${(sentence.score * 100).toFixed(0)}%">${escapeHtml(sentence.sentence)}</mark>`

    lastEnd = sentence.end
  }

  // Add remaining text
  if (lastEnd < text.length) {
    result += escapeHtml(text.slice(lastEnd))
  }

  return result
}

function highlightBySentences(text: string, topSentences: string[]): string {
  let result = escapeHtml(text)

  for (const sentence of topSentences) {
    const escaped = escapeHtml(sentence)
    // Use regex to find and highlight the sentence
    const regex = new RegExp(escapeRegex(escaped), 'gi')
    result = result.replace(
      regex,
      `<mark class="semantic-highlight" title="匹配内容">${escaped}</mark>`
    )
  }

  return result
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
</script>

<style scoped>
.highlighted-text {
  line-height: 1.6;
}

.highlighted-text :deep(.semantic-highlight) {
  background: rgba(250, 204, 21, 0.3);
  padding: 2px 4px;
  border-radius: 3px;
  cursor: help;
  transition: background 0.2s;
}

.highlighted-text :deep(.semantic-highlight:hover) {
  background: rgba(250, 204, 21, 0.5);
}
</style>
