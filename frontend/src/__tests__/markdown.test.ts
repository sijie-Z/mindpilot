/**
 * Tests for markdown utility.
 * Verifies XSS prevention and correct rendering.
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown, escapeHtml } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('renders basic markdown', () => {
    const result = renderMarkdown('**bold** and *italic*')
    expect(result).toContain('<strong>bold</strong>')
    expect(result).toContain('<em>italic</em>')
  })

  it('renders code blocks', () => {
    const result = renderMarkdown('```js\nconst x = 1\n```')
    expect(result).toContain('<code')
    expect(result).toContain('const x = 1')
  })

  it('renders links with safe attributes', () => {
    const result = renderMarkdown('[link](https://example.com)')
    expect(result).toContain('href="https://example.com"')
    expect(result).toContain('target="_blank"')
    expect(result).toContain('rel="noopener noreferrer"')
  })

  it('renders tables', () => {
    const md = '| A | B |\n|---|---|\n| 1 | 2 |'
    const result = renderMarkdown(md)
    expect(result).toContain('<table>')
    expect(result).toContain('<td>1</td>')
  })

  it('returns empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null as any)).toBe('')
    expect(renderMarkdown(undefined as any)).toBe('')
  })

  it('sanitizes script tags', () => {
    const result = renderMarkdown('<script>alert("xss")</script>')
    expect(result).not.toContain('<script>')
    expect(result).not.toContain('alert')
  })

  it('sanitizes event handlers', () => {
    const result = renderMarkdown('<img src=x onerror="alert(1)">')
    expect(result).not.toContain('onerror')
    expect(result).not.toContain('alert')
  })

  it('sanitizes javascript: protocol', () => {
    const result = renderMarkdown('[click](javascript:alert(1))')
    expect(result).not.toContain('javascript:')
  })

  it('preserves code content without sanitizing', () => {
    const result = renderMarkdown('```\n<script>safe code</script>\n```')
    // Code blocks should preserve content
    expect(result).toContain('safe code')
  })

  it('renders headings', () => {
    const result = renderMarkdown('# H1\n## H2\n### H3')
    expect(result).toContain('<h1>')
    expect(result).toContain('<h2>')
    expect(result).toContain('<h3>')
  })

  it('renders lists', () => {
    const result = renderMarkdown('- item 1\n- item 2')
    expect(result).toContain('<ul>')
    expect(result).toContain('<li>item 1</li>')
  })
})

describe('escapeHtml', () => {
  it('escapes ampersand', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b')
  })

  it('escapes angle brackets', () => {
    expect(escapeHtml('<div>')).toBe('&lt;div&gt;')
  })

  it('escapes quotes', () => {
    expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;')
    expect(escapeHtml("'hello'")).toBe('&#039;hello&#039;')
  })

  it('returns empty string for empty input', () => {
    expect(escapeHtml('')).toBe('')
    expect(escapeHtml(null as any)).toBe('')
    expect(escapeHtml(undefined as any)).toBe('')
  })

  it('escapes multiple special chars', () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
    )
  })

  it('leaves safe text unchanged', () => {
    expect(escapeHtml('hello world 123')).toBe('hello world 123')
  })
})
