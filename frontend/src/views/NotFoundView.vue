<template>
  <div class="page">
    <div class="code">404</div>
    <h1>页面不存在</h1>
    <p>您访问的页面可能已被移除</p>
    <button class="btn-primary" @click="$router.push('/chat')">返回首页</button>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  padding: var(--space-8);
  gap: var(--space-3);
}
.code {
  font-size: 96px;
  font-weight: var(--font-bold);
  color: var(--color-primary);
  line-height: 1;
}
h1 {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}
p {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}
.btn-primary {
  padding: var(--space-3) var(--space-6);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background var(--transition-fast);
}
.btn-primary:hover { background: var(--color-primary-hover); }
</style>
