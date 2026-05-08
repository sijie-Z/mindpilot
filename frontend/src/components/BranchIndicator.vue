<template>
  <div class="branch-indicator" v-if="isBranchPoint || isBranched">
    <div class="branch-line" v-if="isBranchPoint">
      <div class="branch-line-segment"></div>
      <div class="branch-node" @click="$emit('branch', messageId)">
        <span class="branch-icon">🌿</span>
        <span class="branch-label">分支</span>
      </div>
    </div>
    <div class="branched-badge" v-if="isBranched">
      <span class="branched-icon">🔀</span>
      <span class="branched-label">已分支</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  messageId: string
  isBranchPoint: boolean
  isBranched: boolean
  branchCount?: number
}>()

defineEmits<{
  branch: [messageId: string]
}>()
</script>

<style scoped>
.branch-indicator {
  position: relative;
  margin-top: 4px;
}

.branch-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.branch-line-segment {
  width: 24px;
  height: 2px;
  background: var(--border-color, #e5e7eb);
}

.branch-node {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-branch, #f0fdf4);
  border: 1px solid var(--border-branch, #86efac);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.branch-node:hover {
  background: var(--bg-branch-hover, #dcfce7);
  border-color: var(--border-branch-hover, #4ade80);
  transform: scale(1.05);
}

.branch-icon {
  font-size: 14px;
}

.branch-label {
  font-size: 12px;
  color: var(--color-branch, #16a34a);
  font-weight: 500;
}

.branched-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-branched, #eff6ff);
  border: 1px solid var(--border-branched, #93c5fd);
  border-radius: 16px;
  margin-top: 4px;
}

.branched-icon {
  font-size: 14px;
}

.branched-label {
  font-size: 12px;
  color: var(--color-branched, #2563eb);
  font-weight: 500;
}
</style>
