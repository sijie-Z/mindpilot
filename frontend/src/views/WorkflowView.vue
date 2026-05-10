<template>
  <div class="page">
    <header class="page-header">
      <h1>工作流管理</h1>
      <div class="header-actions">
        <button class="btn-secondary" @click="showHistory = !showHistory">历史记录</button>
        <button class="btn-primary" @click="showRunModal = true">运行工作流</button>
      </div>
    </header>

    <main class="page-content">
      <div class="workflow-layout">
        <!-- Workflow Graph -->
        <div class="workflow-main">
          <div class="graph-panel">
            <div class="graph-header">
              <h2>RAG 多Agent工作流</h2>
              <div class="legend">
                <span><span class="dot pending"></span>等待</span>
                <span><span class="dot running"></span>执行中</span>
                <span><span class="dot success"></span>成功</span>
                <span><span class="dot error"></span>失败</span>
              </div>
            </div>

            <div class="graph-flow">
              <div class="flow-node start" :class="nodeStatus.start">
                <div class="node-icon">&#9654;</div>
                <div class="node-label">开始</div>
              </div>
              <div class="flow-arrow" :class="{ active: nodeStatus.intent === 'running' }">
                <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              </div>
              <div class="flow-node" :class="nodeStatus.intent">
                <div class="node-icon">&#127919;</div>
                <div class="node-label">意图识别</div>
                <div class="node-desc">分析查询意图</div>
                <div v-if="nodeData.intent" class="node-result">{{ nodeData.intent }}</div>
              </div>
              <div class="flow-arrow" :class="{ active: nodeStatus.retrieval === 'running' }">
                <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              </div>
              <div class="flow-node" :class="nodeStatus.retrieval">
                <div class="node-icon">&#128269;</div>
                <div class="node-label">文档检索</div>
                <div class="node-desc">混合检索 + Rerank</div>
                <div v-if="nodeData.docCount" class="node-result">{{ nodeData.docCount }} 个文档</div>
              </div>
              <div class="flow-arrow" :class="{ active: nodeStatus.answer === 'running' }">
                <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              </div>
              <div class="flow-node" :class="nodeStatus.answer">
                <div class="node-icon">&#9997;</div>
                <div class="node-label">答案生成</div>
                <div class="node-desc">LLM 流式生成</div>
                <div v-if="nodeData.tokens" class="node-result">{{ nodeData.tokens }} tokens</div>
              </div>
              <div class="flow-arrow" :class="{ active: nodeStatus.evaluation === 'running' }">
                <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              </div>
              <div class="flow-node" :class="nodeStatus.evaluation">
                <div class="node-icon">&#128202;</div>
                <div class="node-label">质量评估</div>
                <div class="node-desc">RAGAS 评估</div>
                <div v-if="nodeData.score" class="node-result">得分: {{ nodeData.score.toFixed(2) }}</div>
              </div>
              <div class="flow-arrow">
                <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              </div>
              <div class="flow-node end" :class="nodeStatus.end">
                <div class="node-icon">&#9632;</div>
                <div class="node-label">结束</div>
              </div>
            </div>

            <div v-if="totalTime > 0" class="total-time">
              总耗时: {{ totalTime }}ms
            </div>
          </div>

          <!-- Result Panel -->
          <div v-if="executionResult" class="result-panel">
            <h3>执行结果</h3>
            <div class="result-section">
              <h4>问题</h4>
              <p>{{ executionResult.query }}</p>
            </div>
            <div class="result-section">
              <h4>回答</h4>
              <div class="answer-text" v-html="renderMarkdown(executionResult.answer || '')"></div>
            </div>
            <div v-if="executionResult.sources?.length" class="result-section">
              <h4>来源 ({{ executionResult.sources.length }})</h4>
              <div class="source-tags">
                <span v-for="(s, i) in executionResult.sources" :key="i" class="source-tag">
                  [{{ i + 1 }}] {{ s.filename || s.name || '来源' }}
                </span>
              </div>
            </div>
            <div v-if="executionResult.evaluation" class="result-section">
              <h4>评估指标</h4>
              <div class="eval-metrics">
                <div class="eval-metric">
                  <span class="eval-label">忠实度</span>
                  <span class="eval-value">{{ (executionResult.evaluation.faithfulness || 0).toFixed(2) }}</span>
                </div>
                <div class="eval-metric">
                  <span class="eval-label">相关性</span>
                  <span class="eval-value">{{ (executionResult.evaluation.answer_relevance || 0).toFixed(2) }}</span>
                </div>
                <div class="eval-metric">
                  <span class="eval-label">上下文精度</span>
                  <span class="eval-value">{{ (executionResult.evaluation.context_precision || 0).toFixed(2) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- History Sidebar -->
        <aside v-if="showHistory" class="history-sidebar">
          <div class="sidebar-header">
            <h4>执行历史</h4>
            <button class="icon-btn" @click="showHistory = false">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="history-list">
            <div v-for="(h, i) in history" :key="i" class="history-item" @click="loadHistory(h)">
              <div class="history-query">{{ h.query?.slice(0, 60) }}{{ h.query?.length > 60 ? '...' : '' }}</div>
              <div class="history-meta">
                <span>{{ h.latency_ms }}ms</span>
                <span>{{ formatTime(h.timestamp) }}</span>
              </div>
            </div>
            <div v-if="history.length === 0" class="empty-history">暂无历史记录</div>
          </div>
        </aside>
      </div>
    </main>

    <!-- Run Modal -->
    <div v-if="showRunModal" class="modal-overlay" @click.self="showRunModal = false">
      <div class="modal-panel">
        <div class="modal-header">
          <h2>运行工作流</h2>
          <button class="modal-close" @click="showRunModal = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>输入查询</label>
            <textarea v-model="runQuery" placeholder="输入您的问题..." rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>知识库 ID (可选)</label>
            <input v-model="runKnowledgeId" placeholder="留空使用默认" />
          </div>
          <div class="form-row">
            <label class="checkbox-label"><input type="checkbox" v-model="runStreaming" /> 流式输出</label>
            <label class="checkbox-label"><input type="checkbox" v-model="runEval" /> 启用评估</label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showRunModal = false">取消</button>
          <button class="btn-primary" @click="runWorkflow" :disabled="!runQuery || running">
            {{ running ? '执行中...' : '执行' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import api from '@/api/index'
import { chatApi, type SSEData } from '@/api/chat'

interface Source {
  filename?: string
  name?: string
  chunk_id?: string
  score?: number
}

interface EvaluationResult {
  faithfulness?: number
  answer_relevance?: number
  context_precision?: number
  score?: number
}

interface ExecutionResult {
  query: string
  answer: string
  sources?: Source[]
  evaluation?: EvaluationResult | null
}

interface HistoryItem {
  query: string
  answer?: string
  latency_ms: number
  timestamp: number
  evaluation?: EvaluationResult | null
}

interface NodeStatusMap {
  start: string; intent: string; retrieval: string; answer: string; evaluation: string; end: string
}

const showRunModal = ref(false)
const showHistory = ref(false)
const runQuery = ref('')
const runKnowledgeId = ref('')
const runStreaming = ref(true)
const runEval = ref(true)
const running = ref(false)
const totalTime = ref(0)
const executionResult = ref<ExecutionResult | null>(null)
const history = ref<HistoryItem[]>([])

const nodeStatus = reactive<NodeStatusMap>({
  start: 'pending', intent: 'pending', retrieval: 'pending',
  answer: 'pending', evaluation: 'pending', end: 'pending'
})

const nodeData = reactive({ intent: '', docCount: 0, tokens: 0, score: 0 })

function resetNodes() {
  (Object.keys(nodeStatus) as (keyof NodeStatusMap)[]).forEach(k => { nodeStatus[k] = 'pending' })
  nodeData.intent = ''; nodeData.docCount = 0; nodeData.tokens = 0; nodeData.score = 0
  executionResult.value = null; totalTime.value = 0
}

async function runWorkflow() {
  if (!runQuery.value || running.value) return
  running.value = true; resetNodes(); showRunModal.value = false
  const startTime = Date.now(); nodeStatus.start = 'success'

  if (runStreaming.value) {
    let answerText = ''; const sources: Source[] = []
    nodeStatus.intent = 'running'

    await chatApi.streamChat(
      { query: runQuery.value, knowledge_id: runKnowledgeId.value || undefined },
      {
        onMessage: (data: SSEData) => {
          switch (data.type) {
            case 'intent':
              nodeData.intent = data.content || ''; nodeStatus.intent = 'success'
              nodeStatus.retrieval = 'running'
              break
            case 'retrieval':
              nodeData.docCount = data.count || 0; nodeStatus.retrieval = 'success'
              break
            case 'rerank': nodeStatus.retrieval = 'success'; break
            case 'answer':
              if (data.chunk) {
                answerText += data.content || ''; nodeStatus.answer = 'running'
                nodeData.tokens = Math.round(answerText.length / 4)
              } else {
                answerText = data.content || ''; nodeStatus.answer = 'success'
              }
              break
            case 'source': if (data.source) sources.push(data.source); break
            case 'evaluation':
              nodeStatus.answer = 'success'; nodeStatus.evaluation = 'running'
              if (data.data) nodeData.score = (data.data.faithfulness as number) || (data.data.score as number) || 0
              break
            case 'done':
              nodeStatus.evaluation = 'success'; nodeStatus.end = 'success'
              break
            case 'error':
              const current = (Object.entries(nodeStatus) as [keyof NodeStatusMap, string][]).find(([, v]) => v === 'running')
              if (current) nodeStatus[current[0]] = 'error'
              break
          }
        },
        onError: () => { nodeStatus.answer = 'error' }
      }
    )

    executionResult.value = {
      query: runQuery.value, answer: answerText, sources,
      evaluation: nodeData.score ? { faithfulness: nodeData.score } : null
    }
  } else {
    try {
      nodeStatus.intent = 'running'
      const res = await api.post('/chat/', { query: runQuery.value, knowledge_id: runKnowledgeId.value || undefined })
      nodeStatus.intent = 'success'; nodeStatus.retrieval = 'success'
      nodeStatus.answer = 'success'; nodeStatus.evaluation = 'success'; nodeStatus.end = 'success'
      executionResult.value = res.data
      if (res.data.sources) nodeData.docCount = res.data.sources.length
      if (res.data.evaluation) nodeData.score = res.data.evaluation.faithfulness || 0
    } catch { nodeStatus.answer = 'error' }
  }

  totalTime.value = Date.now() - startTime; running.value = false
  saveToHistory()
}

function saveToHistory() {
  const item = {
    query: runQuery.value,
    answer: executionResult.value?.answer?.slice(0, 200),
    latency_ms: totalTime.value,
    timestamp: Date.now(),
    evaluation: executionResult.value?.evaluation
  }
  history.value.unshift(item)
  if (history.value.length > 20) history.value.pop()
  localStorage.setItem('workflow_history', JSON.stringify(history.value))
}

function loadHistory(item: HistoryItem) {
  runQuery.value = item.query
  executionResult.value = { query: item.query, answer: item.answer, evaluation: item.evaluation }
  showHistory.value = false
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  const saved = localStorage.getItem('workflow_history')
  if (saved) history.value = JSON.parse(saved)
})
</script>

<style scoped>
.page { height: 100%; display: flex; flex-direction: column; background: var(--color-bg); }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-5) var(--space-8);
  background: var(--color-surface); border-bottom: 1px solid var(--color-border);
}
.page-header h1 { font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-text); }
.header-actions { display: flex; gap: var(--space-3); }

.btn-primary {
  padding: var(--space-2) var(--space-4); background: var(--color-primary);
  border: none; border-radius: var(--radius-md); color: #fff;
  font-size: var(--text-sm); font-weight: var(--font-medium); cursor: pointer;
  font-family: var(--font-sans); transition: background var(--transition-fast);
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  padding: var(--space-2) var(--space-4); background: var(--color-bg);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  color: var(--color-text-secondary); font-size: var(--text-sm);
  cursor: pointer; font-family: var(--font-sans); transition: all var(--transition-fast);
}
.btn-secondary:hover { background: var(--color-bg-tertiary); color: var(--color-text); }

/* ── Workflow Layout ── */
.page-content { flex: 1; overflow: hidden; }
.workflow-layout { display: flex; height: 100%; }

.workflow-main { flex: 1; overflow-y: auto; padding: var(--space-6); }

/* Graph */
.graph-panel {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); padding: var(--space-6);
}
.graph-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-6); }
.graph-header h2 { font-size: var(--text-lg); font-weight: var(--font-semibold); color: var(--color-text); }
.legend { display: flex; gap: var(--space-4); font-size: var(--text-xs); color: var(--color-text-secondary); }
.legend span { display: flex; align-items: center; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.pending { background: var(--color-border); }
.dot.running { background: #3b82f6; animation: pulse 1s infinite; }
.dot.success { background: var(--color-success); }
.dot.error { background: var(--color-error); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

.graph-flow { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-4) 0; overflow-x: auto; }

.flow-node {
  min-width: 130px; background: var(--color-bg-secondary); border: 2px solid var(--color-border);
  border-radius: var(--radius-lg); padding: var(--space-4); transition: all 0.3s; position: relative;
}
.flow-node.start, .flow-node.end { min-width: 80px; text-align: center; background: var(--color-bg-tertiary); }
.flow-node.pending { border-color: var(--color-border); }
.flow-node.running { border-color: #3b82f6; background: #eff6ff; box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
.flow-node.success { border-color: var(--color-success); background: var(--color-primary-light); }
.flow-node.error { border-color: var(--color-error); background: #fef2f2; }
.node-icon { font-size: 22px; margin-bottom: var(--space-2); }
.node-label { font-weight: var(--font-semibold); font-size: var(--text-sm); color: var(--color-text); }
.node-desc { font-size: var(--text-xs); color: var(--color-text-tertiary); margin-top: 2px; }
.node-result { font-size: var(--text-xs); color: var(--color-success); margin-top: var(--space-2); font-weight: var(--font-medium); }

.flow-arrow { color: var(--color-border); flex-shrink: 0; }
.flow-arrow.active { color: #3b82f6; animation: arrowPulse 0.5s infinite; }
@keyframes arrowPulse { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(4px); } }

.total-time { text-align: center; margin-top: var(--space-5); padding: var(--space-3); background: var(--color-bg-tertiary); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--color-text); }

/* Result Panel */
.result-panel { margin-top: var(--space-6); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-6); }
.result-panel h3 { font-size: var(--text-lg); font-weight: var(--font-semibold); color: var(--color-text); margin-bottom: var(--space-5); }
.result-section { margin-bottom: var(--space-5); }
.result-section:last-child { margin-bottom: 0; }
.result-section h4 { font-size: var(--text-xs); color: var(--color-text-tertiary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2); }
.result-section p { font-size: var(--text-sm); color: var(--color-text); line-height: var(--leading-normal); }
.answer-text { font-size: var(--text-sm); line-height: var(--leading-relaxed); color: var(--color-text); }
.answer-text :deep(p) { margin-bottom: var(--space-2); }

.source-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.source-tag { padding: var(--space-1) var(--space-3); background: var(--color-bg-tertiary); border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--color-text-secondary); }
.eval-metrics { display: flex; gap: var(--space-6); }
.eval-metric { text-align: center; }
.eval-label { font-size: var(--text-xs); color: var(--color-text-tertiary); }
.eval-value { display: block; font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-primary); }

/* History Sidebar */
.history-sidebar { width: 300px; background: var(--color-surface); border-left: 1px solid var(--color-border); display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-4); border-bottom: 1px solid var(--color-border); }
.sidebar-header h4 { font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--color-text); }
.icon-btn { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; background: none; border: none; border-radius: var(--radius-sm); color: var(--color-text-tertiary); cursor: pointer; }
.icon-btn:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
.history-list { flex: 1; overflow-y: auto; }
.history-item { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--color-border-light); cursor: pointer; transition: background var(--transition-fast); }
.history-item:hover { background: var(--color-bg-secondary); }
.history-query { font-size: var(--text-sm); color: var(--color-text); margin-bottom: var(--space-1); }
.history-meta { display: flex; justify-content: space-between; font-size: var(--text-xs); color: var(--color-text-tertiary); }
.empty-history { padding: var(--space-10); text-align: center; color: var(--color-text-tertiary); font-size: var(--text-sm); }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 200; backdrop-filter: blur(4px); }
.modal-panel { width: 420px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg); overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--color-border); }
.modal-header h2 { font-size: var(--text-lg); font-weight: var(--font-semibold); color: var(--color-text); }
.modal-close { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: none; border: none; border-radius: var(--radius-sm); color: var(--color-text-tertiary); cursor: pointer; }
.modal-close:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
.modal-body { padding: var(--space-5); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-3); padding: var(--space-4) var(--space-5); border-top: 1px solid var(--color-border); background: var(--color-bg-secondary); }

.form-group { margin-bottom: var(--space-4); }
.form-group label { display: block; font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--color-text); margin-bottom: var(--space-2); }
.form-group input, .form-group textarea { width: 100%; padding: var(--space-2) var(--space-3); background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-sans); outline: none; transition: border-color var(--transition-fast); }
.form-group input:focus, .form-group textarea:focus { border-color: var(--color-primary); box-shadow: 0 0 0 2px var(--color-primary-light); }
.form-group textarea { resize: vertical; }
.form-row { display: flex; gap: var(--space-4); margin-bottom: var(--space-4); }
.checkbox-label { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); color: var(--color-text); cursor: pointer; }
.checkbox-label input[type="checkbox"] { accent-color: var(--color-primary); }
</style>
