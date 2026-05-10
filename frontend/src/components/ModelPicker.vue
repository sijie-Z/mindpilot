<template>
  <div class="modal" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <h3>选择模型</h3>
        <button class="modal-close" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div
          v-for="m in models"
          :key="m.id"
          class="model-option"
          :class="{ selected: currentModel === m.id }"
          @click="$emit('select', m.id)"
        >
          <div class="model-name">{{ m.label }}</div>
          <div class="model-desc">{{ m.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface ModelOption {
  id: string
  label: string
  desc: string
}

defineProps<{
  models: ModelOption[]
  currentModel: string
}>()

defineEmits<{
  close: []
  select: [id: string]
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
  width: 360px;
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
.model-option {
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: var(--space-2);
  transition: all var(--transition-fast);
}
.model-option:last-child { margin-bottom: 0; }
.model-option:hover { background: var(--color-bg-tertiary); }
.model-option.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.model-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}
.model-desc {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
</style>
