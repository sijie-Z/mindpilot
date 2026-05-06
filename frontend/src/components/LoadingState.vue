<template>
  <div v-loading="loading" :element-loading-text="text" :element-loading-background="background">
    <slot v-if="!loading" />
    <div v-else-if="placeholder" class="loading-placeholder">
      <!-- Placeholder content shown while loading -->
      <div class="placeholder-icon">
        <el-icon class="is-loading">
          <Loading />
        </el-icon>
      </div>
      <p v-if="text" class="placeholder-text">{{ text }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

interface Props {
  loading?: boolean
  text?: string
  background?: string
  placeholder?: boolean
  spinner?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: true,
  text: '加载中...',
  background: 'rgba(255, 255, 255, 0.7)',
  placeholder: false,
  spinner: true,
})
</script>

<style scoped>
.loading-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 2rem;
  color: var(--el-text-color-secondary);
}

.placeholder-icon {
  margin-bottom: 1rem;
}

.placeholder-icon .el-icon {
  font-size: 32px;
  animation: spin 1s linear infinite;
}

.placeholder-text {
  margin: 0;
  font-size: 14px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>