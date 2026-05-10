<template>
  <div class="modal" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <h3>选择知识库</h3>
        <button class="modal-close" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div v-if="knowledgeBases.length === 0" class="modal-empty">
          <p>暂无知识库</p>
          <router-link to="/knowledge" class="btn-primary" @click="$emit('close')">创建知识库</router-link>
        </div>
        <div v-else class="kb-list">
          <div
            v-for="kb in knowledgeBases"
            :key="kb.id"
            class="kb-item"
            :class="{ selected: selectedId === kb.id }"
            @click="$emit('select', kb)"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
            <div class="kb-info">
              <div class="kb-name">{{ kb.name }}</div>
              <div class="kb-meta">{{ kb.doc_count || 0 }} 文档 · {{ kb.chunk_count || 0 }} 片段</div>
            </div>
            <svg v-if="selectedId === kb.id" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="3">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { KnowledgeBase } from '@/api/types'

defineProps<{
  knowledgeBases: KnowledgeBase[]
  selectedId?: string
}>()

defineEmits<{
  close: []
  select: [kb: KnowledgeBase]
}>()
</script>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}
.modal-panel {
  width: 480px;
  max-height: 480px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border);
}
.modal-header h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}
.modal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
}
.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.modal-body {
  padding: var(--space-4);
  max-height: 360px;
  overflow-y: auto;
}
.modal-empty {
  text-align: center;
  padding: var(--space-8);
  color: var(--color-text-secondary);
}
.modal-empty p { margin-bottom: var(--space-4); }
.btn-primary {
  display: inline-block;
  padding: var(--space-2) var(--space-5);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  text-decoration: none;
}
.btn-primary:hover { background: var(--color-primary-hover); }
.kb-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.kb-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kb-item:hover { background: var(--color-bg-tertiary); }
.kb-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.kb-item svg { color: var(--color-text-tertiary); flex-shrink: 0; }
.kb-item.selected svg { color: var(--color-primary); }
.kb-info { flex: 1; }
.kb-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}
.kb-meta {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
</style>
