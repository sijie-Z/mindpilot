<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo -->
      <div class="login-logo">
        <div class="logo-icon">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <h1>MindPilot</h1>
          <p>智能知识检索平台</p>
        </div>
      </div>

      <!-- Tab switcher -->
      <div class="login-tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <!-- Form -->
      <form @submit.prevent="handleSubmit">
        <div class="field">
          <label>用户名</label>
          <input
            v-model="form.username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
            required
          />
        </div>
        <div class="field">
          <label>密码</label>
          <input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
            required
          />
        </div>
        <div v-if="mode === 'register'" class="field">
          <label>确认密码</label>
          <input
            v-model="form.confirm"
            type="password"
            placeholder="请再次输入密码"
            autocomplete="new-password"
            required
          />
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          <span v-if="loading" class="btn-spinner"></span>
          {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '创建账户') }}
        </button>
      </form>

      <div class="login-footer">
        {{ mode === 'login' ? '还没有账户？' : '已有账户？' }}
        <a @click="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '立即注册' : '立即登录' }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api/index'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ username: '', password: '', confirm: '' })

async function handleSubmit() {
  if (!form.username || !form.password) return

  if (mode.value === 'register') {
    if (form.password !== form.confirm) {
      ElMessage.error('两次密码不一致')
      return
    }
    if (form.password.length < 6) {
      ElMessage.error('密码长度至少6位')
      return
    }
  }

  loading.value = true
  try {
    const url = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const res = await api.post(url, {
      username: form.username,
      password: form.password,
    })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('username', res.data.username || form.username)
    ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
    router.push('/chat')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  padding: var(--space-4);
}

.login-card {
  width: 400px;
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  padding: var(--space-8) var(--space-8) var(--space-6);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-8);
}
.logo-icon {
  width: 48px;
  height: 48px;
  background: var(--color-primary);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.login-logo h1 {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
}
.login-logo p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-top: 2px;
}

/* ── Tabs ── */
.login-tabs {
  display: flex;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
  padding: var(--space-1);
  margin-bottom: var(--space-6);
}
.login-tabs button {
  flex: 1;
  padding: var(--space-2);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}
.login-tabs button.active {
  background: var(--color-primary);
  color: #fff;
}

/* ── Fields ── */
.field {
  margin-bottom: var(--space-4);
}
.field label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.field input {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  transition: border-color var(--transition-fast);
  outline: none;
}
.field input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}
.field input::placeholder {
  color: var(--color-text-tertiary);
}

/* ── Submit ── */
.submit-btn {
  width: 100%;
  padding: var(--space-3);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  font-family: var(--font-sans);
  cursor: pointer;
  margin-top: var(--space-2);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
.submit-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3);
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.login-footer {
  text-align: center;
  margin-top: var(--space-5);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.login-footer a {
  color: var(--color-primary);
  cursor: pointer;
  font-weight: var(--font-medium);
}
.login-footer a:hover { text-decoration: underline; }
</style>
