<template>
  <el-card v-if="type === 'card'" class="skeleton-card" shadow="hover">
    <el-skeleton :rows="rows" animated>
      <template #header>
        <el-skeleton-item variant="h3" style="width: 60%" />
      </template>
    </el-skeleton>
  </el-card>

  <div v-else-if="type === 'list'" class="skeleton-list">
    <div v-for="i in count" :key="i" class="skeleton-list-item">
      <el-skeleton :rows="listRows" animated>
        <template #template>
          <el-skeleton-item variant="text" style="width: 40%" />
          <el-skeleton-item variant="text" style="width: 80%" />
          <el-skeleton-item variant="text" style="width: 60%" />
        </template>
      </el-skeleton>
    </div>
  </div>

  <div v-else-if="type === 'table'" class="skeleton-table">
    <el-skeleton :rows="rows + 1" animated>
      <template #template>
        <el-skeleton-item variant="text" style="width: 100%; margin-bottom: 16px" />
        <el-skeleton-item v-for="i in rows" :key="i" variant="text" style="width: 100%" />
      </template>
    </el-skeleton>
  </div>

  <div v-else class="skeleton-default">
    <el-skeleton :rows="rows" animated />
  </div>
</template>

<script setup lang="ts">
interface Props {
  type?: 'card' | 'list' | 'table' | 'default'
  rows?: number
  count?: number
  listRows?: number
}

withDefaults(defineProps<Props>(), {
  type: 'card',
  rows: 3,
  count: 3,
  listRows: 1,
})
</script>

<style scoped>
.skeleton-card {
  margin-bottom: 1rem;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.skeleton-list-item {
  padding: 1rem;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.skeleton-table {
  width: 100%;
}

.skeleton-default {
  padding: 1rem;
}
</style>