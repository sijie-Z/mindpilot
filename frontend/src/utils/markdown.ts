/**
 * Sanitized markdown rendering utility.
 * Uses DOMPurify to prevent XSS attacks from user/LLM content.
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Open links in new tab with security attributes
const renderer = new marked.Renderer()
renderer.link = function (href: string, title: string, text: string) {
  return `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`
}

// Add copy button to code blocks
renderer.code = function (code: string, language: string) {
  const lang = language || ''
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  const langLabel = lang ? `<span class="code-lang">${lang}</span>` : ''
  return `<div class="code-block">${langLabel}<button class="code-copy-btn" onclick="(function(btn){var t=btn.closest('.code-block').querySelector('code').textContent;navigator.clipboard.writeText(t).then(function(){btn.textContent='已复制';setTimeout(function(){btn.textContent='复制'},1500)});})(this)">复制</button><pre><code class="language-${lang}">${escaped}</code></pre></div>`
}

marked.setOptions({ renderer })

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
      'div', 'span', 'del', 'button',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel', 'onclick'],
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
