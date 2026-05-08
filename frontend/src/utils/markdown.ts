/**
 * Sanitized markdown rendering utility.
 * Uses DOMPurify to prevent XSS attacks from user/LLM content.
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

/**
 * Parse markdown to sanitized HTML.
 * All output is passed through DOMPurify to strip malicious content.
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  const rawHtml = marked.parse(text) as string
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'code', 'pre',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote', 'hr',
      'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'div', 'span', 'del',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
  })
}

/**
 * Escape HTML entities in plain text.
 * Use this when rendering user content as text (not markdown).
 */
export function escapeHtml(text: string): string {
  if (!text) return ''
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return text.replace(/[&<>"']/g, (c) => map[c])
}
