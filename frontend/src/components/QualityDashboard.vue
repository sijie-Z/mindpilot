<template>
  <div class="quality-dashboard">
    <div class="dashboard-header">
      <h2>RAG 质量仪表盘</h2>
      <div class="period-selector">
        <button
          v-for="p in periods"
          :key="p.value"
          :class="{ active: selectedPeriod === p.value }"
          @click="selectedPeriod = p.value; loadDashboard()"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <template v-else>
      <!-- Summary Cards -->
      <div class="summary-cards">
        <div class="metric-card">
          <div class="metric-icon faithfulness">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <div class="metric-info">
            <span class="metric-value">{{ formatPercent(summary.avg_faithfulness) }}</span>
            <span class="metric-label">忠实度</span>
          </div>
          <div class="metric-trend" :class="getTrendClass('faithfulness')">
            {{ getTrendIcon('faithfulness') }}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon relevance">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <div class="metric-info">
            <span class="metric-value">{{ formatPercent(summary.avg_answer_relevance) }}</span>
            <span class="metric-label">答案相关性</span>
          </div>
          <div class="metric-trend" :class="getTrendClass('answer_relevance')">
            {{ getTrendIcon('answer_relevance') }}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon precision">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <div class="metric-info">
            <span class="metric-value">{{ formatPercent(summary.avg_context_precision) }}</span>
            <span class="metric-label">上下文精度</span>
          </div>
          <div class="metric-trend" :class="getTrendClass('context_precision')">
            {{ getTrendIcon('context_precision') }}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon latency">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div class="metric-info">
            <span class="metric-value">{{ formatLatency(summary.avg_latency_ms) }}</span>
            <span class="metric-label">平均延迟</span>
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="charts-row">
        <!-- Trend Chart -->
        <div class="chart-card">
          <h3>质量趋势</h3>
          <div class="chart-container">
            <div class="trend-chart">
              <div class="chart-legend">
                <span class="legend-item faithfulness">忠实度</span>
                <span class="legend-item relevance">相关性</span>
                <span class="legend-item precision">精度</span>
              </div>
              <div class="chart-bars">
                <div v-for="trend in trends" :key="trend.date" class="bar-group">
                  <div class="bar-stack">
                    <div
                      class="bar faithfulness"
                      :style="{ height: (trend.faithfulness * 100) + '%' }"
                      :title="'忠实度: ' + formatPercent(trend.faithfulness)"
                    ></div>
                    <div
                      class="bar relevance"
                      :style="{ height: (trend.answer_relevance * 100) + '%' }"
                      :title="'相关性: ' + formatPercent(trend.answer_relevance)"
                    ></div>
                    <div
                      class="bar precision"
                      :style="{ height: (trend.context_precision * 100) + '%' }"
                      :title="'精度: ' + formatPercent(trend.context_precision)"
                    ></div>
                  </div>
                  <span class="bar-label">{{ formatDate(trend.date) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Distribution Chart -->
        <div class="chart-card">
          <h3>分数分布</h3>
          <div class="chart-container">
            <div class="distribution-chart">
              <div v-for="(count, range) in distributions.faithfulness" :key="range" class="dist-bar">
                <div class="dist-label">{{ range }}</div>
                <div class="dist-track">
                  <div
                    class="dist-fill"
                    :style="{ width: getDistPercent(count) + '%' }"
                  ></div>
                </div>
                <div class="dist-count">{{ count }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Latency Stats -->
      <div class="stats-section">
        <h3>延迟统计</h3>
        <div class="latency-stats">
          <div class="stat-item">
            <span class="stat-label">P50</span>
            <span class="stat-value">{{ formatLatency(latencyStats.median) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">P90</span>
            <span class="stat-value">{{ formatLatency(latencyStats.p90) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">P95</span>
            <span class="stat-value">{{ formatLatency(latencyStats.p95) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">P99</span>
            <span class="stat-value">{{ formatLatency(latencyStats.p99) }}</span>
          </div>
        </div>
      </div>

      <!-- Token Usage -->
      <div class="stats-section">
        <h3>Token 用量</h3>
        <div class="token-stats">
          <div class="stat-item">
            <span class="stat-label">总用量</span>
            <span class="stat-value">{{ formatNumber(tokenUsage.total_tokens) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">平均/查询</span>
            <span class="stat-value">{{ formatNumber(tokenUsage.avg_tokens_per_query) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">总查询</span>
            <span class="stat-value">{{ formatNumber(tokenUsage.total_queries) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/index'

const loading = ref(true)
const selectedPeriod = ref(7)

const periods = [
  { value: 7, label: '7天' },
  { value: 14, label: '14天' },
  { value: 30, label: '30天' },
]

const summary = ref({
  total_evaluations: 0,
  avg_faithfulness: 0,
  avg_answer_relevance: 0,
  avg_context_precision: 0,
  avg_latency_ms: 0,
  total_tokens: 0,
})

const trends = ref<Array<{
  date: string
  faithfulness: number
  answer_relevance: number
  context_precision: number
}>>([])

const distributions = ref<Record<string, Record<string, number>>>({
  faithfulness: {},
  answer_relevance: {},
  context_precision: {},
})

const latencyStats = ref({
  median: 0,
  p90: 0,
  p95: 0,
  p99: 0,
})

const tokenUsage = ref({
  total_tokens: 0,
  total_queries: 0,
  avg_tokens_per_query: 0,
})

onMounted(() => {
  loadDashboard()
})

async function loadDashboard() {
  loading.value = true
  try {
    const [summaryRes, trendsRes, distRes, latencyRes, tokenRes] = await Promise.all([
      api.get('/admin/evaluations/summary', { params: { days: selectedPeriod.value } }),
      api.get('/analytics/quality/trends', { params: { days: selectedPeriod.value } }),
      api.get('/analytics/quality/distribution', { params: { days: selectedPeriod.value } }),
      api.get('/analytics/quality/latency', { params: { days: selectedPeriod.value } }),
      api.get('/analytics/tokens/usage', { params: { days: selectedPeriod.value } }),
    ])

    summary.value = summaryRes.data
    trends.value = trendsRes.data?.trends || []
    distributions.value = distRes.data?.distributions || {}
    latencyStats.value = latencyRes.data?.stats || {}
    tokenUsage.value = tokenRes.data || {}
  } catch (error) {
    console.error('Failed to load dashboard:', error)
  } finally {
    loading.value = false
  }
}

function formatPercent(value: number): string {
  return (value * 100).toFixed(1) + '%'
}

function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return (ms / 1000).toFixed(1) + 's'
  }
  return Math.round(ms) + 'ms'
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function getTrendClass(metric: string): string {
  // Simple trend calculation based on recent values
  const trendData = trends.value.slice(-3)
  if (trendData.length < 2) return ''

  const first = trendData[0][metric as keyof typeof trendData[0]] as number
  const last = trendData[trendData.length - 1][metric as keyof typeof trendData[0]] as number

  if (last > first * 1.05) return 'trend-up'
  if (last < first * 0.95) return 'trend-down'
  return 'trend-stable'
}

function getTrendIcon(metric: string): string {
  const cls = getTrendClass(metric)
  if (cls === 'trend-up') return '↑'
  if (cls === 'trend-down') return '↓'
  return '→'
}

function getDistPercent(count: number): number {
  const maxCount = Math.max(...Object.values(distributions.value.faithfulness || {}))
  return maxCount > 0 ? (count / maxCount) * 100 : 0
}
</script>

<style scoped>
.quality-dashboard {
  padding: 24px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.dashboard-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1f2937);
}

.period-selector {
  display: flex;
  gap: 4px;
  background: var(--bg-secondary, #f3f4f6);
  padding: 4px;
  border-radius: 8px;
}

.period-selector button {
  padding: 8px 16px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  transition: all 0.2s;
}

.period-selector button.active {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #1f2937);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 60px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color, #e5e7eb);
  border-top-color: var(--color-primary, #3b82f6);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-secondary, #f9fafb);
  border-radius: 12px;
  border: 1px solid var(--border-color, #e5e7eb);
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-icon.faithfulness {
  background: #dbeafe;
  color: #2563eb;
}

.metric-icon.relevance {
  background: #dcfce7;
  color: #16a34a;
}

.metric-icon.precision {
  background: #fef3c7;
  color: #d97706;
}

.metric-icon.latency {
  background: #f3e8ff;
  color: #9333ea;
}

.metric-info {
  flex: 1;
}

.metric-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary, #1f2937);
}

.metric-label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  margin-top: 4px;
}

.metric-trend {
  font-size: 18px;
  font-weight: 600;
}

.metric-trend.trend-up {
  color: #16a34a;
}

.metric-trend.trend-down {
  color: #dc2626;
}

.metric-trend.trend-stable {
  color: #6b7280;
}

/* Charts */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.chart-card {
  background: var(--bg-secondary, #f9fafb);
  border-radius: 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  padding: 20px;
}

.chart-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #1f2937);
  margin-bottom: 16px;
}

.chart-container {
  height: 200px;
}

/* Trend Chart */
.trend-chart {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.legend-item {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-item::before {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.legend-item.faithfulness::before { background: #3b82f6; }
.legend-item.relevance::before { background: #22c55e; }
.legend-item.precision::before { background: #f59e0b; }

.chart-bars {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.bar-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.bar-stack {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 2px;
}

.bar {
  width: 100%;
  min-height: 4px;
  border-radius: 2px 2px 0 0;
  transition: height 0.3s;
}

.bar.faithfulness { background: #3b82f6; }
.bar.relevance { background: #22c55e; }
.bar.precision { background: #f59e0b; }

.bar-label {
  font-size: 10px;
  color: var(--text-tertiary, #9ca3af);
  margin-top: 4px;
}

/* Distribution Chart */
.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dist-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dist-label {
  width: 60px;
  font-size: 11px;
  color: var(--text-secondary, #6b7280);
  text-align: right;
}

.dist-track {
  flex: 1;
  height: 20px;
  background: var(--bg-tertiary, #f3f4f6);
  border-radius: 4px;
  overflow: hidden;
}

.dist-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 4px;
  transition: width 0.3s;
}

.dist-count {
  width: 30px;
  font-size: 12px;
  color: var(--text-primary, #1f2937);
  font-weight: 500;
}

/* Stats Sections */
.stats-section {
  background: var(--bg-secondary, #f9fafb);
  border-radius: 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  padding: 20px;
  margin-bottom: 16px;
}

.stats-section h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #1f2937);
  margin-bottom: 16px;
}

.latency-stats,
.token-stats {
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1f2937);
}

/* Responsive */
@media (max-width: 768px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-row {
    grid-template-columns: 1fr;
  }

  .latency-stats,
  .token-stats {
    flex-wrap: wrap;
  }
}
</style>
