<template>
  <div class="page">
    <header class="page-header">
      <h1>系统设置</h1>
    </header>

    <main class="page-content">
      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="tab-btn"
          :class="{ active: activeTab === t.key }"
          @click="activeTab = t.key"
        >{{ t.label }}</button>
      </div>

      <!-- Model Config -->
      <div v-if="activeTab === 'model'" class="panel">
        <h2>模型配置</h2>
        <div class="form-row">
          <div class="form-field">
            <label>LLM 模型</label>
            <select v-model="modelSettings.model">
              <option value="glm-4-flash">GLM-4-Flash (快速)</option>
              <option value="glm-4">GLM-4 (标准)</option>
              <option value="glm-4v-plus">GLM-4V-Plus (多模态)</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Embedding 模型</label>
            <select v-model="modelSettings.embedding">
              <option value="embedding-3">Embedding-3</option>
            </select>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="saveModelSettings">保存配置</button>
        </div>
      </div>

      <!-- Retrieval Config -->
      <div v-if="activeTab === 'retrieval'" class="panel">
        <h2>混合检索配置</h2>
        <div class="form-row">
          <div class="form-field">
            <label>向量检索权重</label>
            <div class="slider-row">
              <input type="range" min="0" max="100" v-model.number="vectorWeight" />
              <span class="slider-value">{{ vectorWeight }}%</span>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>BM25 权重（自动计算）</label>
            <div class="weight-display">
              <div class="weight-bar">
                <div class="weight-fill vector" :style="{ width: vectorWeight + '%' }"></div>
                <div class="weight-fill bm25" :style="{ width: (100 - vectorWeight) + '%' }"></div>
              </div>
              <div class="weight-labels">
                <span>向量 {{ vectorWeight }}%</span>
                <span>BM25 {{ 100 - vectorWeight }}%</span>
              </div>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Top K</label>
            <input type="number" v-model.number="retrievalSettings.top_k" min="1" max="50" />
          </div>
          <div class="form-field">
            <label class="checkbox-label">
              <input type="checkbox" v-model="retrievalSettings.rerank_enabled" />
              启用 Rerank
            </label>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="saveRetrievalSettings">保存配置</button>
        </div>
      </div>

      <!-- System Settings -->
      <div v-if="activeTab === 'system'" class="panel">
        <h2>系统参数</h2>
        <div class="settings-grid">
          <div class="setting-item" v-for="(val, key) in systemSettings" :key="key">
            <span class="setting-key">{{ key }}</span>
            <span class="setting-val">{{ val }}</span>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-secondary" @click="loadSystemSettings">刷新</button>
        </div>
      </div>

      <!-- API Key Management -->
      <div v-if="activeTab === 'apikey'" class="panel">
        <h2>API Key 管理</h2>
        <p class="panel-desc">API Key 用于通过 API 接口访问 MindPilot 服务。</p>
        <div class="apikey-section">
          <div v-if="myApiKey" class="apikey-display">
            <label>您的 API Key</label>
            <div class="apikey-row">
              <code class="apikey-value">{{ myApiKey }}</code>
              <button class="btn-secondary" @click="copyApiKey">复制</button>
            </div>
            <p class="apikey-warn">请妥善保管，此 Key 仅显示一次。</p>
          </div>
          <div v-else class="apikey-empty">
            <p>您还没有 API Key。</p>
          </div>
          <div class="apikey-actions">
            <button class="btn-primary" @click="generateApiKey">
              {{ myApiKey ? '重新生成' : '生成 API Key' }}
            </button>
            <button v-if="myApiKey" class="btn-danger" @click="revokeApiKey">撤销 Key</button>
          </div>
        </div>
      </div>

      <!-- Audit Logs -->
      <div v-if="activeTab === 'audit'" class="panel">
        <h2>操作日志</h2>
        <div class="audit-toolbar">
          <select v-model="auditFilter" @change="loadAuditLogs">
            <option value="">全部操作</option>
            <option value="login">登录</option>
            <option value="register">注册</option>
            <option value="document_upload">文档上传</option>
            <option value="document_delete">文档删除</option>
          </select>
          <button class="btn-secondary" @click="loadAuditLogs">刷新</button>
        </div>
        <div class="audit-table">
          <div class="audit-header">
            <span>时间</span><span>用户</span><span>操作</span><span>详情</span>
          </div>
          <div v-for="log in auditLogs" :key="log.id" class="audit-row">
            <span class="audit-time">{{ formatTime(log.created_at) }}</span>
            <span class="audit-user">{{ log.username || '-' }}</span>
            <span class="audit-action">{{ log.action }}</span>
            <span class="audit-detail">{{ log.detail || '-' }}</span>
          </div>
          <div v-if="auditLogs.length === 0" class="audit-empty">暂无日志</div>
        </div>
        <div class="audit-pagination" v-if="auditTotal > 20">
          <button class="btn-secondary" :disabled="auditPage === 0" @click="auditPage--; loadAuditLogs()">上一页</button>
          <span>{{ auditPage * 20 + 1 }}-{{ Math.min((auditPage + 1) * 20, auditTotal) }} / {{ auditTotal }}</span>
          <button class="btn-secondary" :disabled="(auditPage + 1) * 20 >= auditTotal" @click="auditPage++; loadAuditLogs()">下一页</button>
        </div>
      </div>

      <!-- System Monitor -->
      <div v-if="activeTab === 'monitor'" class="panel">
        <h2>系统监控</h2>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-value">{{ stats.total_queries || 0 }}</div>
            <div class="metric-label">总查询数</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{{ stats.avg_latency || 0 }}<small>ms</small></div>
            <div class="metric-label">平均延迟</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{{ stats.token_usage || '0' }}</div>
            <div class="metric-label">Token 用量</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{{ stats.avg_score || '0.00' }}</div>
            <div class="metric-label">平均质量分</div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-secondary" @click="refreshStats">刷新</button>
        </div>
      </div>

      <!-- Skill Stats -->
      <div v-if="activeTab === 'skills'" class="panel">
        <h2>技能使用统计</h2>
        <div class="skill-grid">
          <div v-for="(data, name) in skillStats" :key="name" class="skill-card">
            <div class="skill-header">
              <span class="skill-name">{{ name }}</span>
              <span class="skill-badge" :class="(data.live?.success_rate ?? 0) > 0.8 ? 'badge-ok' : 'badge-warn'">
                {{ ((data.live?.success_rate ?? 0) * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="skill-metrics">
              <div class="skill-metric">
                <span class="metric-num">{{ data.live?.call_count || 0 }}</span>
                <span class="metric-lbl">本次调用</span>
              </div>
              <div class="skill-metric">
                <span class="metric-num">{{ data.historical?.total_calls_30d || 0 }}</span>
                <span class="metric-lbl">30天总计</span>
              </div>
              <div class="skill-metric">
                <span class="metric-num">{{ data.live?.avg_latency_ms || 0 }}<small>ms</small></span>
                <span class="metric-lbl">平均延迟</span>
              </div>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-secondary" @click="loadSkillStats">刷新</button>
        </div>
      </div>

      <!-- Quality Dashboard -->
      <div v-if="activeTab === 'quality'" class="panel panel-full">
        <QualityDashboard />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import QualityDashboard from '@/components/QualityDashboard.vue'
import { adminApi, type SkillStats } from '@/api/admin'
import api from '@/api/index'

const activeTab = ref('model')
const vectorWeight = ref(70)

const tabs = [
  { key: 'model', label: '模型配置' },
  { key: 'retrieval', label: '检索设置' },
  { key: 'system', label: '系统参数' },
  { key: 'apikey', label: 'API Key' },
  { key: 'audit', label: '操作日志' },
  { key: 'skills', label: '技能统计' },
  { key: 'monitor', label: '系统监控' },
  { key: 'quality', label: '质量仪表盘' },
]

const modelSettings = reactive({ model: 'glm-4-flash', embedding: 'embedding-3' })
const retrievalSettings = reactive({ top_k: 10, rerank_enabled: true })
const stats = reactive<{ total_queries: number; avg_latency: number; token_usage: string; avg_score: number }>({
  total_queries: 0, avg_latency: 0, token_usage: '0', avg_score: 0,
})
const skillStats = ref<SkillStats>({})
const systemSettings = ref<Record<string, unknown>>({})
const myApiKey = ref<string | null>(null)
const auditLogs = ref<any[]>([])
const auditTotal = ref(0)
const auditPage = ref(0)
const auditFilter = ref('')

onMounted(() => { loadSettings(); loadSkillStats(); loadSystemSettings() })

async function loadSettings() {
  try {
    const cfg = await adminApi.getRetrievalConfig()
    if (cfg) {
      vectorWeight.value = Math.round((cfg.vector_weight || 0.7) * 100)
      retrievalSettings.top_k = cfg.top_k || 10
      retrievalSettings.rerank_enabled = cfg.rerank_enabled ?? true
    }
  } catch { /* use defaults */ }

  try {
    const data = await adminApi.getSystemStats()
    Object.assign(stats, data || {})
  } catch { /* unavailable */ }
}

async function saveModelSettings() {
  try {
    await adminApi.updateRetrievalConfig({
      llm_model: modelSettings.model,
      embedding_model: modelSettings.embedding,
    })
    ElMessage.success('模型配置已保存')
  } catch { ElMessage.error('保存失败') }
}

async function saveRetrievalSettings() {
  try {
    await adminApi.updateRetrievalConfig({
      vector_weight: vectorWeight.value / 100,
      bm25_weight: (100 - vectorWeight.value) / 100,
      top_k: retrievalSettings.top_k,
      rerank_enabled: retrievalSettings.rerank_enabled,
    })
    ElMessage.success('检索配置已保存')
  } catch { ElMessage.error('保存失败') }
}

async function refreshStats() {
  try {
    const data = await adminApi.getSystemStats()
    Object.assign(stats, data || {})
    ElMessage.success('已刷新')
  } catch { ElMessage.error('刷新失败') }
}

async function loadSkillStats() {
  try {
    skillStats.value = await adminApi.getSkillStats()
  } catch { /* unavailable */ }
}

async function loadSystemSettings() {
  try {
    const res = await api.get('/admin/settings')
    systemSettings.value = res.data
  } catch { /* unavailable */ }
}

async function loadApiKey() {
  try {
    const res = await api.get('/admin/api-key')
    myApiKey.value = res.data?.api_key || null
  } catch { /* unavailable */ }
}

async function generateApiKey() {
  try {
    const res = await api.post('/admin/api-key')
    myApiKey.value = res.data?.api_key
    ElMessage.success('API Key 已生成')
  } catch { ElMessage.error('生成失败') }
}

async function revokeApiKey() {
  if (!confirm('确定撤销 API Key？使用此 Key 的应用将无法访问。')) return
  try {
    await api.delete('/admin/api-key')
    myApiKey.value = null
    ElMessage.success('API Key 已撤销')
  } catch { ElMessage.error('撤销失败') }
}

function copyApiKey() {
  if (myApiKey.value) {
    navigator.clipboard.writeText(myApiKey.value)
    ElMessage.success('已复制')
  }
}

async function loadAuditLogs() {
  try {
    const params: Record<string, unknown> = { limit: 20, skip: auditPage.value * 20 }
    if (auditFilter.value) params.action = auditFilter.value
    const res = await api.get('/admin/audit-logs', { params })
    auditLogs.value = res.data?.logs || []
    auditTotal.value = res.data?.total || 0
  } catch { /* unavailable */ }
}

function formatTime(ts: string) {
  if (!ts) return '-'
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  loadApiKey()
  loadAuditLogs()
})
</script>

<style scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}

.page-header {
  padding: var(--space-5) var(--space-8);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.page-header h1 {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

/* ── Tabs ── */
.tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
  width: fit-content;
  margin-bottom: var(--space-6);
}
.tab-btn {
  padding: var(--space-2) var(--space-4);
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
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active {
  background: var(--color-surface);
  color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

/* ── Panel ── */
.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}
.panel-full {
  max-width: none;
  padding: 0;
  border: none;
  background: transparent;
}
.panel h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  margin-bottom: var(--space-6);
}

.form-row {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-5);
}
.form-field {
  flex: 1;
}
.form-field label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.form-field select, .form-field input[type="number"] {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-text);
  font-family: var(--font-sans);
  outline: none;
  transition: border-color var(--transition-fast);
}
.form-field select:focus, .form-field input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}
.form-field input[type="number"] { max-width: 120px; }

.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  margin-top: var(--space-6);
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}

.slider-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.slider-row input[type="range"] {
  flex: 1;
  accent-color: var(--color-primary);
}
.slider-value {
  font-weight: var(--font-semibold);
  color: var(--color-primary);
  min-width: 40px;
}

.weight-display { margin-top: var(--space-3); }
.weight-bar {
  height: 8px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-full);
  display: flex;
  overflow: hidden;
}
.weight-fill.vector {
  background: var(--color-primary);
  border-radius: var(--radius-full) 0 0 var(--radius-full);
  transition: width var(--transition-normal);
}
.weight-fill.bm25 {
  background: var(--color-warning);
  border-radius: 0 var(--radius-full) var(--radius-full) 0;
  transition: width var(--transition-normal);
}
.weight-labels {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.form-actions {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.btn-primary {
  padding: var(--space-2) var(--space-5);
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

.btn-secondary {
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all var(--transition-fast);
}
.btn-secondary:hover { background: var(--color-bg-tertiary); color: var(--color-text); }

/* ── Metrics ── */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}
.metric-card {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  text-align: center;
}
.metric-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-primary);
}
.metric-value small {
  font-size: var(--text-sm);
  font-weight: var(--font-normal);
  color: var(--color-text-tertiary);
}
.metric-label {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: var(--space-1);
}

/* ── Skill Cards ── */
.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

/* System settings */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}
.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.setting-key {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}
.setting-val {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
  font-family: var(--font-mono);
}
.skill-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}
.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.skill-name {
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  color: var(--color-text);
}
.skill-badge {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-weight: var(--font-medium);
}
.badge-ok {
  background: var(--color-success-bg, #e6f9ee);
  color: var(--color-success, #22c55e);
}
.badge-warn {
  background: var(--color-warning-bg, #fef3cd);
  color: var(--color-warning, #f59e0b);
}
.skill-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}
.skill-metric {
  text-align: center;
}
.metric-num {
  display: block;
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--color-primary);
}
.metric-num small {
  font-size: var(--text-xs);
  font-weight: var(--font-normal);
  color: var(--color-text-tertiary);
}
.metric-lbl {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* API Key */
.panel-desc {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}
.apikey-section {
  max-width: 500px;
}
.apikey-display {
  margin-bottom: var(--space-4);
}
.apikey-display label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.apikey-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.apikey-value {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text);
  word-break: break-all;
}
.apikey-warn {
  font-size: var(--text-xs);
  color: var(--color-warning);
  margin-top: var(--space-2);
}
.apikey-empty p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}
.apikey-actions {
  display: flex;
  gap: var(--space-3);
}
.btn-danger {
  padding: var(--space-2) var(--space-4);
  background: var(--color-error);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  cursor: pointer;
}
.btn-danger:hover {
  opacity: 0.9;
}

/* Audit Logs */
.audit-toolbar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.audit-toolbar select {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-text);
  background: var(--color-surface);
}
.audit-table {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.audit-header, .audit-row {
  display: grid;
  grid-template-columns: 140px 100px 140px 1fr;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
}
.audit-header {
  background: var(--color-bg-secondary);
  font-weight: var(--font-semibold);
  color: var(--color-text-secondary);
}
.audit-row {
  border-top: 1px solid var(--color-border-light);
  color: var(--color-text);
}
.audit-row:hover {
  background: var(--color-bg-secondary);
}
.audit-time {
  color: var(--color-text-tertiary);
  font-size: var(--text-xs);
}
.audit-action {
  font-weight: var(--font-medium);
}
.audit-detail {
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.audit-empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}
.audit-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
</style>
