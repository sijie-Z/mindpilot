<template>
  <div class="branch-tree">
    <div class="branch-header">
      <span class="branch-icon">🌿</span>
      <span class="branch-title">对话分支</span>
      <button class="branch-close" @click="$emit('close')">&times;</button>
    </div>

    <div class="branch-list">
      <!-- Main branch -->
      <div
        class="branch-item"
        :class="{ active: !currentBranchId }"
        @click="$emit('switch', null)"
      >
        <div class="branch-dot main"></div>
        <div class="branch-info">
          <div class="branch-name">主线对话</div>
          <div class="branch-meta">{{ mainBranch.message_count }} 条消息</div>
        </div>
      </div>

      <!-- Other branches -->
      <div
        v-for="branch in branches"
        :key="branch.id"
        class="branch-item"
        :class="{ active: currentBranchId === branch.id }"
        @click="$emit('switch', branch.id)"
      >
        <div class="branch-dot"></div>
        <div class="branch-info">
          <div class="branch-name">{{ branch.name }}</div>
          <div class="branch-meta">
            {{ branch.message_count }} 条消息 · {{ formatTime(branch.created_at) }}
          </div>
        </div>
        <button
          class="branch-delete"
          @click.stop="$emit('delete', branch.id)"
          title="删除分支"
        >
          &times;
        </button>
      </div>
    </div>

    <div class="branch-actions">
      <button
        class="branch-action-btn"
        @click="$emit('create')"
        :disabled="!canCreateBranch"
      >
        <span>+</span> 从当前消息创建分支
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Branch {
  id: string
  name: string
  parent_message_id: string
  message_count: number
  created_at: string
}

defineProps<{
  branches: Branch[]
  mainBranch: { message_count: number }
  currentBranchId: string | null
  canCreateBranch: boolean
}>()

defineEmits<{
  switch: [branchId: string | null]
  create: []
  delete: [branchId: string]
  close: []
}>()

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} 小时前`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} 天前`

  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.branch-tree {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: 300px;
  max-height: 400px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.branch-header {
  display: flex;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  gap: 8px;
}

.branch-icon {
  font-size: 20px;
}

.branch-title {
  flex: 1;
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary, #1f2937);
}

.branch-close {
  background: none;
  border: none;
  font-size: 20px;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.branch-close:hover {
  color: var(--text-primary, #1f2937);
}

.branch-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.branch-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  gap: 12px;
  transition: background-color 0.2s;
}

.branch-item:hover {
  background: var(--bg-hover, #f3f4f6);
}

.branch-item.active {
  background: var(--bg-active, #eff6ff);
  border: 1px solid var(--border-active, #3b82f6);
}

.branch-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-gray, #9ca3af);
  flex-shrink: 0;
}

.branch-dot.main {
  background: var(--color-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.branch-info {
  flex: 1;
  min-width: 0;
}

.branch-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #1f2937);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.branch-meta {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  margin-top: 2px;
}

.branch-delete {
  background: none;
  border: none;
  font-size: 16px;
  color: var(--text-secondary, #9ca3af);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  opacity: 0;
  transition: all 0.2s;
}

.branch-item:hover .branch-delete {
  opacity: 1;
}

.branch-delete:hover {
  color: var(--color-danger, #ef4444);
  background: rgba(239, 68, 68, 0.1);
}

.branch-actions {
  padding: 12px;
  border-top: 1px solid var(--border-color, #e5e7eb);
}

.branch-action-btn {
  width: 100%;
  padding: 10px 16px;
  background: var(--bg-primary, #fff);
  border: 1px dashed var(--border-color, #d1d5db);
  border-radius: 8px;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.branch-action-btn:hover:not(:disabled) {
  border-color: var(--color-primary, #3b82f6);
  color: var(--color-primary, #3b82f6);
  background: var(--bg-hover, #f9fafb);
}

.branch-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.branch-action-btn span {
  font-size: 18px;
  font-weight: 500;
}
</style>
