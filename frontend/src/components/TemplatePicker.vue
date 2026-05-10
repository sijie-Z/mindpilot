<template>
  <div class="modal" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <h3>提示词模板</h3>
        <div class="header-actions">
          <button class="add-btn" @click="showCreate = !showCreate" title="新建模板">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button class="modal-close" @click="$emit('close')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Create form -->
      <div v-if="showCreate" class="create-form">
        <input v-model="newTitle" placeholder="模板标题" class="form-input" />
        <textarea v-model="newContent" placeholder="模板内容" class="form-textarea" rows="3"></textarea>
        <div class="form-actions">
          <select v-model="newCategory" class="form-select">
            <option value="general">通用</option>
            <option value="writing">写作</option>
            <option value="analysis">分析</option>
            <option value="code">代码</option>
            <option value="translate">翻译</option>
          </select>
          <button class="save-btn" @click="handleCreate" :disabled="!newTitle.trim() || !newContent.trim()">保存</button>
        </div>
      </div>

      <!-- Category filter -->
      <div class="category-tabs">
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="cat-tab"
          :class="{ active: activeCategory === cat.key }"
          @click="activeCategory = cat.key"
        >{{ cat.label }}</button>
      </div>

      <!-- Template list -->
      <div class="modal-body">
        <div
          v-for="tpl in filteredTemplates"
          :key="tpl.id"
          class="template-item"
        >
          <div class="template-info" @click="$emit('select', tpl.content)">
            <div class="template-title">{{ tpl.title }}</div>
            <div class="template-preview">{{ tpl.content.slice(0, 60) }}{{ tpl.content.length > 60 ? '...' : '' }}</div>
          </div>
          <button
            v-if="tpl.is_owner"
            class="delete-btn"
            @click.stop="handleDelete(tpl.id)"
            title="删除"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div v-if="filteredTemplates.length === 0" class="empty-text">
          该分类下暂无模板
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { templatesApi, type PromptTemplate } from '@/api/templates'

defineEmits<{
  close: []
  select: [content: string]
}>()

const templates = ref<PromptTemplate[]>([])
const activeCategory = ref('all')
const showCreate = ref(false)
const newTitle = ref('')
const newContent = ref('')
const newCategory = ref('general')

const categories = [
  { key: 'all', label: '全部' },
  { key: 'general', label: '通用' },
  { key: 'writing', label: '写作' },
  { key: 'analysis', label: '分析' },
  { key: 'code', label: '代码' },
  { key: 'translate', label: '翻译' },
]

const filteredTemplates = computed(() => {
  if (activeCategory.value === 'all') return templates.value
  return templates.value.filter(t => t.category === activeCategory.value)
})

onMounted(async () => {
  await loadTemplates()
})

async function loadTemplates() {
  try {
    templates.value = await templatesApi.list()
  } catch (err) {
    console.warn('Failed to load templates:', err)
  }
}

async function handleCreate() {
  if (!newTitle.value.trim() || !newContent.value.trim()) return
  try {
    await templatesApi.create({
      title: newTitle.value.trim(),
      content: newContent.value.trim(),
      category: newCategory.value,
    })
    newTitle.value = ''
    newContent.value = ''
    showCreate.value = false
    await loadTemplates()
  } catch (err) {
    console.error('Failed to create template:', err)
  }
}

async function handleDelete(id: string) {
  try {
    await templatesApi.delete(id)
    templates.value = templates.value.filter(t => t.id !== id)
  } catch (err) {
    console.error('Failed to delete template:', err)
  }
}
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
  width: 420px;
  max-height: 520px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
.header-actions {
  display: flex;
  gap: var(--space-2);
}
.add-btn, .modal-close {
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
.add-btn:hover, .modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

/* Create form */
.create-form {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}
.form-input {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  background: var(--color-surface);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.form-textarea {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  background: var(--color-surface);
  color: var(--color-text);
  resize: vertical;
  margin-bottom: var(--space-2);
}
.form-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}
.form-select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  background: var(--color-surface);
  color: var(--color-text);
}
.save-btn {
  padding: var(--space-1) var(--space-3);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: var(--text-xs);
  cursor: pointer;
}
.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Category tabs */
.category-tabs {
  display: flex;
  padding: var(--space-2) var(--space-4);
  gap: var(--space-1);
  border-bottom: 1px solid var(--color-border);
}
.cat-tab {
  padding: var(--space-1) var(--space-2);
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  cursor: pointer;
}
.cat-tab:hover { background: var(--color-bg-tertiary); }
.cat-tab.active {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: var(--font-medium);
}

/* Template list */
.modal-body {
  padding: var(--space-3);
  overflow-y: auto;
  flex: 1;
}
.template-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-1);
  transition: background var(--transition-fast);
}
.template-item:hover { background: var(--color-bg-secondary); }
.template-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.template-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}
.template-preview {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.delete-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.template-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover { color: var(--color-error); background: #fef2f2; }
.empty-text {
  text-align: center;
  padding: var(--space-6);
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}
</style>
