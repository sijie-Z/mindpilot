# MindPilot - 多模态智能知识检索与多端协作平台

## 项目概述

**MindPilot** 是一款基于 RAG + 多Agent 协作的智能知识检索系统，支持文档、图片、截图的多模态理解，无缝接入网页 / QQ / 飞书等多端。

### 核心能力
- 多格式文档解析：PDF / Word / PPT，支持扫描件 OCR
- 多模态理解：图片问答、截图解析、架构图分析
- 精准检索：语义 + 关键词混合检索，自动重排序
- 多Agent协作：意图识别 → 检索 → 生成 → 评估，全链路编排
- 多端接入：网页对话 + QQ机器人 + 飞书机器人
- 安全加固：bcrypt 密码、JWT 认证、XSS 防护、注入防护
- 企业级部署：Docker Compose 编排、网络隔离、健康检查、限流

---

## 一、技术架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│   │   Vue 3 前端    │  │   QQ 机器人    │  │   飞书机器人    │              │
│   │  Element Plus   │  │   (NoneBot2)   │  │   (WebHook)     │              │
│   │  SSE 流式渲染   │  │  群聊@使用     │  │  企业内部使用    │              │
│   │  DOMPurify XSS  │  │  私聊对话      │  │                 │              │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
└─────────────────────────────── Nginx (80) ──────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI 后端 (8000)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      LangGraph 多Agent编排                             │ │
│  │                                                                        │ │
│  │   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐                │ │
│  │   │ Intent │───▶│Retrieval│───▶│ Answer │───▶│  Eval  │                │ │
│  │   │ (意图) │    │+Rerank │    │ (流式  │    │ (RAGAS │                │ │
│  │   │        │    │        │    │ 生成)  │    │ 评估)  │                │ │
│  │   └────────┘    └────────┘    └────────┘    └────────┘                │ │
│  │                                                                        │ │
│  │   SSE状态回传：「正在理解问题」「正在扩展搜索」「正在重排序」...        │ │
│  │                                                                        │ │
│  │   Skill系统：自动注册 + 意图路由 + 遥测追踪 (6个Skill)               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        RAG Pipeline                                    │ │
│  │                                                                        │ │
│  │   文档上传 ──▶ 解析（文字/OCR）──▶ 切片 ──▶ 向量化（智谱）           │ │
│  │                            │                                           │ │
│  │                      文本存MySQL + 向量存Milvus（双写回滚）            │ │
│  │                            │                                           │ │
│  │   查询 ──▶ Query Expansion ──▶ 混合检索（权重可调）                    │ │
│  │                            │                                           │ │
│  │                      Rerank（从MySQL取内容）                           │ │
│  │                            │                                           │ │
│  │                      Self-RAG校验 + 流式生成                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        安全与中间件                                    │ │
│  │                                                                        │ │
│  │   bcrypt 密码哈希 │ JWT + API Key 认证 │ 请求限流 (Redis 滑动窗口)   │ │
│  │   XSS 防护 (DOMPurify) │ Milvus 注入防护 │ Prompt 注入扫描           │ │
│  │   ErrorClassifier │ ContextEngine │ StreamScrubber │ MemoryManager   │ │
│  │   统一异常体系 │ Prometheus 指标 │ LangFuse 追踪                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        数据存储层                                     │ │
│  │                                                                        │ │
│  │   MySQL 8.0 (元数据 + ngram全文索引)                                  │ │
│  │   Milvus 2.3 (向量存储, HNSW索引)                                     │ │
│  │   Redis 7 (会话缓存 + 限流计数)                                       │ │
│  │   MySQL+Milvus 双写一致性（回滚机制）                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Docker 部署                                    │ │
│  │                                                                        │ │
│  │   8 服务编排：MySQL + Redis + Milvus + etcd + MinIO + Backend          │ │
│  │              + Frontend + Nginx                                        │ │
│  │   网络隔离：internal (DB/Milvus) + external (Nginx/Frontend)          │ │
│  │   健康检查：所有服务配置 healthcheck                                  │ │
│  │   资源限制：每个服务设置 memory limits                                 │ │
│  │   非 root 容器：backend/frontend 使用专用用户                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、项目结构

```
mindpilot/
├── backend/                          # 后端项目
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口 + 中间件链
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── auth.py                   # JWT/API Key 认证 (bcrypt)
│   │   │
│   │   ├── api/                      # API 路由
│   │   │   ├── chat.py               # 对话 API (SSE 流式 + 非流式)
│   │   │   ├── document.py           # 文档上传 + 后台处理
│   │   │   ├── knowledge.py          # 知识库 CRUD
│   │   │   ├── admin.py              # 管理后台 (用户/统计/评估)
│   │   │   ├── analytics.py          # RAG 质量分析 (趋势/分布/延迟)
│   │   │   ├── auth.py               # 登录/注册
│   │   │   ├── branches.py           # 对话分支 CRUD
│   │   │   ├── health.py             # 健康检查 + Prometheus
│   │   │   ├── highlight.py          # 语义搜索高亮
│   │   │   ├── image.py              # 图片问答
│   │   │   ├── feishu.py             # 飞书 Webhook
│   │   │   └── workflow.py           # 工作流 API
│   │   │
│   │   ├── agents/                   # LangGraph Agent 编排
│   │   │   ├── graph.py              # Agent 状态图 (LangGraph)
│   │   │   ├── intent_agent.py       # 意图识别
│   │   │   ├── retrieval_agent.py    # 检索 + Query Expansion
│   │   │   ├── answer_agent.py       # 生成 (流式 + Self-RAG)
│   │   │   ├── eval_agent.py         # RAGAS 质量评估
│   │   │   ├── self_rag.py           # Self-RAG 自检
│   │   │   ├── state.py              # AgentState TypedDict
│   │   │   └── workflow.py           # 自定义工作流引擎
│   │   │
│   │   ├── core/                     # 基础设施
│   │   │   ├── llm_client.py         # LLM 客户端 (智谱 + 重试)
│   │   │   ├── logger.py             # 结构化日志 (structlog)
│   │   │   ├── exceptions.py         # 统一异常体系
│   │   │   ├── error_classifier.py   # 错误分类 + 恢复提示
│   │   │   ├── context_engine.py     # 可插拔上下文管理 + 压缩
│   │   │   ├── stream_scrubber.py    # SSE 流式上下文清洗
│   │   │   ├── injection_scanner.py  # Prompt 注入扫描
│   │   │   ├── memory_manager.py     # 记忆管理器 (预取/同步)
│   │   │   ├── curator.py            # RAG 索引维护代理
│   │   │   ├── metrics.py            # Prometheus 指标
│   │   │   ├── observability.py      # LangFuse 追踪
│   │   │   ├── rate_limit.py         # 滑动窗口限流 (Redis)
│   │   │   ├── retry.py              # 指数退避 + 去相关抖动 + 熔断
│   │   │   └── container.py          # 依赖注入容器
│   │   │
│   │   ├── rag/                      # RAG Pipeline
│   │   │   ├── parser.py             # 文档解析 (PDF/Word/PPT)
│   │   │   ├── chunker.py            # 文本切片 (语义分块)
│   │   │   ├── embedder.py           # 向量化 (智谱 Embedding-3)
│   │   │   ├── retriever.py          # 混合检索 (Vector + BM25 + RRF)
│   │   │   ├── reranker.py           # BGE Reranker 重排序
│   │   │   ├── vector_store.py       # Milvus 向量库 (HNSW)
│   │   │   ├── faiss_store.py        # FAISS 本地备选
│   │   │   └── consistency.py        # 数据一致性 (双写回滚)
│   │   │
│   │   ├── multimodal/               # 多模态
│   │   │   ├── ocr.py                # PaddleOCR 扫描件识别
│   │   │   └── vision.py             # GLM-4V 图片理解
│   │   │
│   │   ├── skills/                   # Skill 系统 (自动注册 + 遥测)
│   │   │   ├── base.py               # Skill 基类
│   │   │   ├── registry.py           # 自动发现注册表 + 遥测追踪
│   │   │   ├── calc_skill.py         # 计算器 (calculation 意图)
│   │   │   ├── search_skill.py       # 网络搜索 (search 意图)
│   │   │   ├── rag_skill.py          # RAG 检索 (doc_qa 意图)
│   │   │   ├── image_skill.py        # 图片理解 (image 意图)
│   │   │   ├── code_skill.py         # 代码执行 (code 意图，沙箱)
│   │   │   └── analysis_skill.py     # 数据分析 (analysis 意图，CSV/JSON)
│   │   │
│   │   ├── storage/                  # 存储
│   │   │   ├── database.py           # MySQL (aiomysql)
│   │   │   ├── redis_client.py       # Redis 封装
│   │   │   ├── models.py             # ORM 模型
│   │   │   └── session_repo.py       # 会话持久化
│   │   │
│   │   └── utils/
│   │       └── mcp.py                # MCP 协议实现
│   │
│   ├── alembic/                      # 数据库迁移
│   │   └── versions/
│   │       ├── 001_initial_schema.py # 初始 Schema
│   │       └── 002_conversation_branches.py # 对话分支
│   ├── tests/                        # 测试
│   ├── init.sql                      # MySQL 初始化脚本
│   ├── Dockerfile                    # 多阶段构建 (非 root)
│   ├── pyproject.toml                # pytest + ruff + mypy 配置
│   └── requirements.txt
│
├── frontend/                         # 前端项目
│   ├── src/
│   │   ├── api/                      # API 封装
│   │   │   ├── index.ts              # Axios 实例 + 拦截器
│   │   │   ├── types.ts              # 共享类型定义
│   │   │   ├── branches.ts           # 对话分支 API
│   │   │   ├── chat.ts               # SSE 流式 + AbortController
│   │   │   ├── highlight.ts          # 语义高亮 API
│   │   │   ├── knowledge.ts          # 知识库 API
│   │   │   └── admin.ts              # 管理 API
│   │   ├── views/                    # 页面
│   │   │   ├── ChatView.vue          # 对话 (SSE 流式渲染)
│   │   │   ├── KnowledgeView.vue     # 知识库列表
│   │   │   ├── KnowledgeDetailView.vue
│   │   │   ├── AdminView.vue         # 管理后台
│   │   │   ├── WorkflowView.vue      # 工作流可视化
│   │   │   ├── ChatHistoryView.vue   # 历史对话
│   │   │   └── LoginView.vue         # 登录
│   │   ├── components/               # 组件
│   │   │   ├── DocumentPreview.vue   # 文档预览
│   │   │   ├── LoadingState.vue      # 加载状态
│   │   │   ├── SkeletonCard.vue      # 骨架屏
│   │   │   ├── BranchTree.vue        # 分支树面板
│   │   │   ├── BranchIndicator.vue   # 分支点指示器
│   │   │   ├── HighlightedText.vue   # 语义高亮文本
│   │   │   └── QualityDashboard.vue  # RAG 质量仪表盘
│   │   ├── stores/                   # Pinia 状态管理
│   │   │   ├── app.ts                # 全局状态 (清理/媒体查询)
│   │   │   ├── chat.ts               # 对话状态 (SSE + 缓存)
│   │   │   └── knowledge.ts          # 知识库状态
│   │   ├── composables/              # 组合式函数
│   │   │   └── useConfirm.ts         # 确认对话框
│   │   ├── utils/
│   │   │   └── markdown.ts           # DOMPurify + marked 渲染
│   │   ├── router/
│   │   │   └── index.ts              # Vue Router (401 事件驱动)
│   │   └── __tests__/                # 单元测试
│   │       ├── setup.ts              # 测试环境配置
│   │       ├── markdown.test.ts      # 工具函数测试
│   │       ├── stores.test.ts        # Pinia Store 测试
│   │       ├── router.test.ts        # 路由配置测试
│   │       ├── api.test.ts           # API 层测试
│   │       └── components.test.ts    # 组件测试
│   ├── e2e/                          # Playwright E2E
│   ├── nginx.conf                    # SPA + SSE 代理
│   ├── Dockerfile                    # 多阶段 (Node + Nginx)
│   ├── vite.config.ts                # 代码分割 + 代理配置
│   ├── vitest.config.ts              # Vitest 测试配置
│   └── package.json
│
├── bot/                              # QQ 机器人
│   ├── bot.py                        # NoneBot2 入口
│   └── plugins/
│       ├── chat.py                   # 对话插件
│       └── admin.py                  # 管理插件
│
├── nginx/
│   └── nginx.conf                    # 反向代理 + 安全头 + 限流
│
├── mysql/
│   └── init.sql                      # Docker 初始化脚本
│
├── docker-compose.yml                # 8 服务编排
├── .env.example                      # 环境变量模板
├── .github/workflows/
│   ├── ci.yml                        # CI 流水线 (lint, test, build, docker)
│   └── release.yml                   # Release 流水线 (tag触发, Docker推送)
└── README.md
```

---

## 三、关键实现细节

### 3.1 安全体系

**密码安全：** bcrypt 哈希，不存储明文
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_hash = pwd_context.hash(password)
```

**XSS 防护：** 前端 DOMPurify 清理所有 LLM 输出
```typescript
import DOMPurify from 'dompurify'
const safeHtml = DOMPurify.sanitize(rawHtml, {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', ...],
  ALLOW_DATA_ATTR: false,
})
```

**注入防护：** Milvus 查询 ID 正则清洗
```python
import re
safe_id = re.sub(r'[^a-zA-Z0-9\-_]', '', knowledge_id)
```

**SSE 中断：** 前端 AbortController 支持取消流式请求
```typescript
const controller = new AbortController()
fetch('/api/chat/stream', { signal: controller.signal, ... })
// 取消: controller.abort()
```

---

### 3.2 MySQL + Milvus 数据一致性

```python
# backend/app/rag/consistency.py

class DataConsistencyManager:
    """
    MySQL + Milvus 双写一致性管理

    策略：先写MySQL，再写Milvus
    - 如果Milvus写入失败，回滚MySQL
    - 删除时采用双删策略
    """

    async def insert_chunks_with_rollback(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        knowledge_id: str,
        doc_id: str,
    ) -> bool:
        chunk_ids = [c["id"] for c in chunks]
        try:
            # 1. 先写MySQL（文本+元数据）
            await self.mysql_insert(chunks)
            # 2. 再写Milvus（向量）
            await self.milvus_insert(chunk_ids, embeddings, knowledge_id)
            return True
        except Exception:
            # 回滚：删除MySQL中的数据
            await self.mysql_delete(chunk_ids)
            return False
```

**面试话术**：
> "MySQL和Milvus的数据一致性，我通过异常捕获+回滚机制解决。写入时先写MySQL再写Milvus，如果Milvus失败就回滚MySQL。删除时采用双删策略，确保两边数据一致。"

---

### 3.3 MySQL 全文搜索优化（ngram）

```sql
-- ngram 分词器支持中文按词分词
CREATE FULLTEXT INDEX content_fulltext ON chunks (content) WITH PARSER ngram;
```

```python
# 混合检索：向量 + BM25 + RRF 融合
async def hybrid_search(self, query, knowledge_id, top_k=10):
    vector_results = await self.vector_search(query, knowledge_id)
    bm25_results = await self.bm25_search(query, knowledge_id)
    # RRF (Reciprocal Rank Fusion) 融合
    return self.rrf_fusion(vector_results, bm25_results, top_k)
```

**面试话术**：
> "MySQL自带的FULLTEXT对中文支持不好，默认按空格分词。我配置了ngram分词器，让它能正确地按中文词语分词，配合向量检索做RRF融合，检索效果显著提升。"

---

### 3.4 SSE 流式响应

```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        # 状态回传
        yield f"data: {json.dumps({'type': 'status', 'content': '正在理解您的问题...'})}\n\n"
        # 意图识别
        state = await intent_node(state, llm=llm)
        yield f"data: {json.dumps({'type': 'intent', 'content': state['intent']})}\n\n"
        # 流式生成
        async for chunk in generate_answer_stream(query, docs, llm):
            yield f"data: {json.dumps({'type': 'answer', 'content': chunk, 'chunk': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

**Nginx SSE 配置**：
```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;
    add_header X-Accel-Buffering no;
}
```

**面试话术**：
> "SSE部署时有个坑：Nginx默认会缓存代理响应，导致前端收不到流。配置proxy_buffering off和X-Accel-Buffering no确保实时推送。前端用fetch+getReader()接收，同时支持AbortController取消。"

---

### 3.5 多模态处理

```python
# PaddleOCR 扫描件识别
class OCRProcessor:
    async def extract_text_from_image(self, image_path: str) -> str:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='ch')
        result = ocr.ocr(image_path, cls=True)
        # ... 提取文字

# GLM-4V 图片理解
class VisionProcessor:
    async def understand_image(self, image_base64: str, query: str) -> str:
        response = client.chat.completions.create(
            model="glm-4v-plus",
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                {"type": "text", "text": query}
            ]}]
        )
        return response.choices[0].message.content
```

---

### 3.6 Agent 设计模式（参考 Hermes Agent）

MindPilot 借鉴了 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)（138k+ stars）的核心设计模式：

#### 3.6.1 错误分类与恢复提示

```python
# backend/app/core/error_classifier.py
class FailoverReason(str, Enum):
    AUTH = "auth"
    BILLING = "billing"
    RATE_LIMIT = "rate_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    ...

def classify(exception: Exception) -> ErrorClassification:
    """分类错误并返回恢复提示：retryable, should_compress, should_fallback"""
    # 快速路径：异常类型查找
    # 慢速路径：正则模式匹配
```

#### 3.6.2 可插拔上下文引擎

```python
# backend/app/core/context_engine.py
class ContextEngine:
    """
    生命周期钩子：on_session_start → add_message → build_messages
    → update_from_response → should_compress → compress → on_session_end
    """
    def __init__(self, strategy: CompressionStrategy | str = "summarize"):
        self._strategy = SummarizeStrategy(llm=llm)  # 或 TruncationStrategy
```

#### 3.6.3 流式上下文清洗

```python
# backend/app/core/stream_scrubber.py
class StreamScrubber:
    """状态机：防止系统提示、内部ID、调试信息泄漏到SSE流"""
    # 过滤：prompt模板、embedding_id、rerank_score、session UUID
    # 保留：代码块内容（不清洗代码）
```

#### 3.6.4 Prompt 注入扫描

```python
# backend/app/core/injection_scanner.py
class InjectionScanner:
    """扫描检索到的文档，检测注入攻击后再送入LLM"""
    # 检测：直接覆盖、角色操纵、数据窃取、编码伪装
    # 集成点：retrieval_agent.py 的 Step 4
```

#### 3.6.5 记忆管理器

```python
# backend/app/core/memory_manager.py
class MemoryManager:
    """预取/同步生命周期，解耦记忆与热路径"""
    async def prefetch_all(session_id, user_id, query) -> MemoryContext
    async def sync_all(session_id, user_id, response)
```

#### 3.6.6 Curator 索引维护

```python
# backend/app/core/curator.py
class Curator:
    """后台维护代理：修剪过期嵌入、合并重复块、验证一致性"""
    async def run_maintenance(knowledge_id) -> MaintenanceResult
```

**面试话术**：
> "Agent 设计参考了 Hermes Agent 的几个核心模式：错误分类器把异常分成结构化类别，每类带恢复提示（重试/压缩/降级），避免散落的 try/except。上下文引擎用生命周期钩子管理对话窗口，压缩时保护头部和尾部消息。流式清洗器是状态机，防止系统提示和内部 ID 泄漏到 SSE 流。注入扫描器在检索结果送入 LLM 前检测攻击模式。"

---

### 3.7 Docker 部署架构

```yaml
# docker-compose.yml - 8 服务编排
services:
  mysql:     # 内部网络, healthcheck, 1G 内存限制
  redis:     # 内部网络, 密码保护
  milvus:    # 内部网络, 依赖 etcd + minio
  etcd:      # Milvus 依赖
  minio:     # Milvus 依赖
  backend:   # 内部+外部网络, 依赖 mysql/redis/milvus
  frontend:  # 外部网络, 依赖 backend
  nginx:     # 外部网络, 唯一对外端口 (80)

networks:
  internal:  # DB/Milvus 不对外暴露
    internal: true
  external:  # Nginx/Frontend
```

**面试话术**：
> "Docker部署用了网络隔离：数据库和向量库在internal网络，外部无法直接访问。只有nginx在external网络对外暴露80端口。所有服务都配置了healthcheck和内存限制，确保容器健康。"

---

### 3.8 测试体系

**后端测试 (pytest)：**
- 单元测试：Agent、RAG Pipeline、Skills、ErrorClassifier、StreamScrubber、InjectionScanner
- 集成测试：API 端点、数据库、Redis
- 负载测试：并发对话、SSE 流式、Milvus 操作
- 覆盖率：pytest-cov + HTML 报告

**前端测试 (Vitest)：**
- 工具函数测试：markdown.ts (XSS 防护、escapeHtml)
- Store 测试：app/chat/knowledge store 状态管理
- 路由测试：路由配置、导航守卫
- 组件测试：SkeletonCard、LoadingState、NotFoundView
- API 类型测试：类型定义、SSE 事件类型

**运行测试：**
```bash
# 后端单元测试
cd backend && pytest tests/ -v -m "not integration"

# 后端覆盖率
pytest tests/ -v --cov=app --cov-report=html

# 前端测试
cd frontend && npm test

# 前端测试覆盖率
npm run test:coverage

# 前端测试 UI
npm run test:ui
```

### 3.9 CI/CD 流水线

**GitHub Actions CI (ci.yml)：**
1. Backend Lint：ruff check + format
2. Frontend Lint：vue-tsc type check
3. Frontend Test：vitest + coverage 上传
4. Frontend Build：vite build + artifact 上传
5. Backend Test：pytest + MySQL/Redis 服务 + coverage 上传
6. Docker Build：backend/frontend 镜像构建 (仅 main 分支)
7. Deploy Preview：PR 评论提示

**GitHub Actions Release (release.yml)：**
- 触发条件：push tag (v*)
- 构建 Docker 镜像
- 推送到 GitHub Container Registry
- 自动生成 changelog
- 创建 GitHub Release

**面试话术**：
> "CI/CD 用 GitHub Actions 实现：每次 PR 自动运行 lint、test、build。main 分支推送会构建 Docker 镜像。打 tag 时自动发布到 GitHub Container Registry 并创建 Release。前端测试用 Vitest，后端用 pytest，都有覆盖率报告。"

---

### 3.10 对话分支（Conversation Branching）

支持从任意消息点创建对话分支，实现类似 ChatGPT 的 Branch 功能。

**数据模型：**
```python
# backend/app/storage/models.py
class ConversationBranch(Base):
    __tablename__ = "conversation_branches"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"))
    parent_message_id = Column(String(36), nullable=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

# Message 模型增加 branch_id 外键
class Message(Base):
    branch_id = Column(String(36), ForeignKey("conversation_branches.id", ondelete="SET NULL"))
```

**分支创建流程：**
```python
# backend/app/api/branches.py
async def create_branch(session_id, parent_message_id, name):
    # 1. 创建分支记录
    # 2. 复制主分支中 parent_message_id 之前的所有消息到新分支
    # 3. 新消息的 branch_id 指向新分支
    # 4. 支持从主分支或子分支继续创建子分支
```

**前端集成：**
- `BranchTree.vue` — 分支树面板，显示主分支 + 所有子分支
- `BranchIndicator.vue` — 消息上的分支点标记
- ChatView 中每条助手消息显示「分叉」按钮

**面试话术**：
> "对话分支的核心是消息的 branch_id 字段。创建分支时，把分支点之前的消息复制一份并标记新 branch_id，后续消息自动归属新分支。查询时按 branch_id 过滤，切换分支只需改变当前 branch_id。这种设计不需要修改原有消息表结构，只加了一个可空外键。"

---

### 3.11 语义搜索高亮（Semantic Search Highlighting）

检索结果中按句子级相关性精准高亮，帮助用户快速定位关键信息。

**核心算法：**
```python
# backend/app/api/highlight.py
def split_sentences(text: str) -> list[str]:
    """正则分句，支持中英文混合"""
    # 中文句号、问号、感叹号 + 英文标点

async def compute_sentence_scores(query, sentences):
    """句子级相关性评分"""
    # 1. 用 Embedding 模型计算 query 和每个句子的向量
    # 2. 余弦相似度作为相关性分数
    # 3. 兜底：关键词匹配（无 Embedding 时）
```

**前端渲染：**
```vue
<!-- HighlightedText.vue -->
<template>
  <span v-for="(part, i) in parts" :key="i">
    <mark v-if="part.highlighted" :style="{ opacity: 0.3 + part.score * 0.7 }">
      {{ part.text }}
    </mark>
    <span v-else>{{ part.text }}</span>
  </span>
</template>
```

**集成点：** KnowledgeDetailView 检索测试结果自动调用 `/api/highlight/chunks` 进行语义高亮。

**面试话术**：
> "语义高亮不是简单的关键词匹配。我用 Embedding 模型把 query 和每个句子都转成向量，算余弦相似度得到相关性分数。高亮时用 opacity 表达相关度强弱，越相关的句子黄色越深。没有 Embedding 服务时会降级到关键词匹配。"

---

### 3.12 RAG 质量仪表盘（RAG Quality Dashboard）

基于 RAGAS 评估数据的可视化仪表盘，实时监控 RAG 系统质量。

**后端 API（5 个端点）：**
```python
# backend/app/api/analytics.py
GET /analytics/quality/trends      # 每日质量趋势（忠实度/相关性/精度）
GET /analytics/quality/distribution # 分数分布直方图
GET /analytics/quality/latency     # 延迟百分位（P50/P90/P95/P99）
GET /analytics/tokens/usage        # Token 用量统计
GET /admin/evaluations/summary     # 质量指标汇总
```

**前端组件（QualityDashboard.vue）：**
- **汇总卡片**：忠实度、答案相关性、上下文精度、平均延迟（含趋势箭头）
- **趋势图表**：每日质量指标柱状图
- **分布图表**：分数区间分布直方图
- **延迟统计**：P50/P90/P95/P99 百分位
- **Token 用量**：总量、平均/查询、总查询数
- **时间选择**：7天/14天/30天

**集成方式：** AdminView 新增「质量仪表盘」Tab，以 `panel-full` 模式全宽渲染。

**面试话术**：
> "质量仪表盘基于 RAGAS 评估数据。每次对话后 EvalAgent 会计算忠实度、答案相关性、上下文精度三个维度的分数并存入 evaluations 表。仪表盘从这个表聚合数据，展示趋势、分布和延迟百分位。前端用纯 CSS 实现柱状图和直方图，没有引入额外图表库，保持轻量。"

---

## 四、开发优先级

| 阶段 | 优先级 | 功能 | 说明 |
|------|--------|------|------|
| **Phase 1** | P0 | FastAPI 骨架 + 对话 API | 核心入口 |
| | P0 | LangGraph 单 Agent | Agent 能力 |
| | P0 | RAG 基础 (解析+切片) | 核心技术 |
| **Phase 2** | P1 | MySQL + Milvus 存储 | 数据持久化 |
| | P1 | 智谱 Embedding | 向量化 |
| | P1 | 混合检索 + Rerank | 检索优化 |
| **Phase 3** | P1 | 多 Agent 协作 | 完整流程 |
| | P1 | SSE 状态回传 | 用户体验 |
| | P1 | Vue 前端 | 演示界面 |
| **Phase 4** | P2 | 数据一致性 (回滚) | 工程细节 |
| | P2 | PaddleOCR + VLM | 多模态 |
| | P2 | QQ 机器人 | 多端接入 |
| | P2 | 安全加固 | bcrypt/XSS/注入 |
| | P2 | Docker 生产部署 | 网络隔离/健康检查 |

---

## 五、环境变量

```bash
# 智谱 API（主力）
ZHIPU_API_KEY=your-zhipu-api-key

# 数据库
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mindpilot
MYSQL_PASSWORD=xxx
MYSQL_DATABASE=mindpilot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=xxx

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 安全 (必须修改)
SECRET_KEY=generate-with-python-c-import-secrets-print-secrets-token-urlsafe-64

# 可观测性（可选）
LANGFUSE_PUBLIC_KEY=xxx
LANGFUSE_SECRET_KEY=xxx
```

---

## 六、简历关键词

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         MindPilot 简历关键词                              │
├──────────────────────────────────────────────────────────────────────────┤
│  多Agent编排    │ LangGraph 状态机、意图识别、SSE 状态回传               │
│  RAG 全链路     │ 文档解析、切片、混合检索 (权重可调)、Rerank、Self-RAG  │
│  多模态处理     │ PaddleOCR、GLM-4V 图片理解、VLM 描述生成              │
│  数据一致性     │ MySQL+Milvus 双写、回滚机制、双删策略                  │
│  中文检索优化   │ ngram 全文索引、BM25 融合、RRF 算法                    │
│  安全工程       │ bcrypt 密码、DOMPurify XSS、注入防护、JWT 认证        │
│  工程实践       │ FastAPI、Pydantic、Docker Compose、网络隔离            │
│  可观测性       │ LangFuse 追踪、Prometheus 指标、结构化日志             │
│  前端工程       │ Vue3 + Pinia + Element Plus、SSE 流式、代码分割        │
│  Agent 模式     │ Skill 自动注册、意图路由、遥测追踪、Fire-and-forget    │
│  会话搜索       │ MySQL FULLTEXT + ngram 中文分词、跨会话历史检索        │
│  错误恢复       │ ErrorClassifier、FailoverReason、恢复提示、去相关抖动  │
│  安全防护       │ Prompt 注入扫描、SSE 上下文清洗、沙箱代码执行          │
│  上下文管理     │ ContextEngine 生命周期、压缩策略、MemoryManager       │
│  测试工程       │ Vitest + Vue Test Utils、pytest + coverage、E2E       │
│  CI/CD         │ GitHub Actions、Docker 自动构建、自动发布              │
│  对话分支      │ Branch 复制策略、分支树可视化、branch_id 隔离          │
│  语义高亮      │ Embedding 余弦相似度、句子级评分、opacity 渐变渲染    │
│  质量仪表盘    │ RAGAS 指标聚合、趋势图表、延迟百分位、Token 分析      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 七、代码质量审计与修复记录 (v4.1)

### 7.1 安全修复

| 问题 | 文件 | 修复 |
|------|------|------|
| **限流绕过** | `core/rate_limit.py` | 移除 `X-User-ID` header 信任，改为纯 IP 限流 |
| **代码执行沙箱逃逸** | `skills/code_skill.py` | 将 `eval()/exec()` 替换为 subprocess 隔离执行，真实超时保护 |
| **变量遮蔽** | `core/rate_limit.py` | `for key, value` 遮蔽外部 rate-limit key 变量，重命名为 `header_key` |
| **死代码/悬垂方法** | `storage/session_repo.py` | 删除 `search_messages` 后的孤立 `save_evaluation` 代码块 |

### 7.2 Bug 修复

| 问题 | 文件 | 修复 |
|------|------|------|
| **Graph 每次重建** | `agents/graph.py` | 缓存编译后的 graph 实例，避免每次 `run_agent` 重新编译 |
| **SSEData 类型不匹配** | `api/chat.ts` | `content` 类型改为 `string \| string[]`，匹配 expansion 事件 |
| **双重 HTML 转义** | `components/HighlightedText.vue` | `escapeHtml` 改为纯字符串替换，避免 DOM 创建开销 |
| **分页数据丢失** | `api/knowledge.ts` | `list()` 支持 `{ items, total }` 分页响应格式 |
| **引用相等断言** | `__tests__/stores.test.ts` | `toBe` → `toStrictEqual`，适配 Pinia 响应式代理 |
| **Router props 断言** | `__tests__/router.test.ts` | `toBe(true)` → `toBeTruthy()`，适配 Vue Router 对象包装 |
| **链接缺少安全属性** | `utils/markdown.ts` | 添加自定义 marked renderer，链接自动带 `target="_blank"` + `rel="noopener noreferrer"` |
| **日志保留字冲突** | `skills/registry.py` | `module=` → `skill_module=`，避免 structlog LogRecord 覆盖 |

### 7.3 优化

| 优化项 | 文件 | 说明 |
|--------|------|------|
| **Graph 缓存** | `agents/graph.py` | 编译后的 StateGraph 缓存复用，消除每次调用的编译开销 |
| **Embedder 快速失败** | `rag/embedder.py` | 移除静默零向量替换，批量嵌入失败时抛出异常，防止脏数据进入向量库 |
| **Markdown 链接安全** | `utils/markdown.ts` | 外部链接自动 `target="_blank"` + `rel="noopener noreferrer"` |
| **SSE 流式类型安全** | `api/chat.ts` | SSEData.content 支持联合类型，消除运行时类型不匹配 |

### 7.4 测试覆盖

```
后端：126 passed, 48 deselected (integration), 覆盖率 63%
前端：64 passed, 0 failed
总计：190 tests all green
```

---

## 八、功能完善与优化 (v4.2)

### 8.1 后端 Skills 完善

| Skill | 改进 | 说明 |
|-------|------|------|
| **search_skill.py** | 重写 | 支持 `JINA_API_KEY` 环境变量、可配置超时 (`SEARCH_TIMEOUT`)、指数重试 (`MAX_RETRIES`)、区分 HTTP 客户端/服务端错误 |
| **image_skill.py** | 重写 | ZhipuAI 客户端单例复用（不再每次新建）、支持直接传入 `image_base64`（无需文件路径）、参数类型化 |

### 8.2 检索优化

| 优化项 | 文件 | 说明 |
|--------|------|------|
| **BM25 BOOLEAN MODE** | `rag/retriever.py` | `NATURAL LANGUAGE MODE` → `BOOLEAN MODE`，解决中文短词被 `ft_min_word_len` 过滤的问题。`+term` AND 逻辑确保所有关键词匹配 |
| **Token 估算精度** | `core/context_engine.py` | 新增 `estimate_tokens()` 函数：CJK 字符 ×1.5、ASCII 字符 ×0.35、其他 ×0.5，替代粗糙的 `len//2` |

### 8.3 前端组件拆分

从 `ChatView.vue`（原 1263 行）提取 3 个独立组件：

| 组件 | 职责 | 代码行 |
|------|------|--------|
| `KnowledgePicker.vue` | 知识库选择弹窗 | ~140 |
| `ModelPicker.vue` | 模型选择弹窗 | ~100 |
| `SearchModal.vue` | 历史对话搜索弹窗（含 API 调用） | ~160 |

**ChatView.vue** 减少约 300 行，模板更清晰。

### 8.4 前端类型安全

| 修复 | 文件 | 说明 |
|------|------|------|
| `any[]` → `KnowledgeBase[]` | `ChatView.vue` | `knowledgeBases` 使用强类型 |
| `any` → `KnowledgeBase \| null` | `ChatView.vue` | `selectedKnowledge` 使用强类型 |
| 直接 mutation → store 方法 | `ChatView.vue` | `switchBranch` 改用 `clearMessages()` + `addMessage()` |

### 8.5 测试覆盖新增

新增 12 个测试用例：

| 测试类 | 测试数 | 覆盖模块 |
|--------|--------|----------|
| `TestTokenEstimation` | 6 | `context_engine.py` token 估算 |
| `TestCuratorExtended` | 2 | `curator.py` 配置和数据结构 |
| `TestSearchSkill` | 2 | `search_skill.py` 边界条件 |
| `TestImageSkill` | 2 | `image_skill.py` 边界条件 |

```
后端：138 passed (+12), 覆盖率 63%
前端：64 passed
总计：202 tests all green
```

---

## 九、类型安全与 API 层优化 (v4.3)

### 9.1 WorkflowView.vue 类型安全

| 修复 | 说明 |
|------|------|
| `any` → `ExecutionResult` | 定义 `Source`、`EvaluationResult`、`ExecutionResult`、`HistoryItem` 接口 |
| `any[]` → `HistoryItem[]` | 历史记录使用强类型 |
| `any[]` → `Source[]` | 来源数据使用强类型 |
| `loadHistory(item: any)` → `loadHistory(item: HistoryItem)` | 函数参数类型化 |
| 移除重复 `formatMarkdown` | 直接使用 `@/utils/markdown` 的 `renderMarkdown` |

### 9.2 AdminView.vue API 层统一

| 修复 | 说明 |
|------|------|
| `api.get/put` → `adminApi` 方法 | 所有配置读写改用 `adminApi.getRetrievalConfig()`、`updateRetrievalConfig()`、`getSystemStats()` |
| 新增 `adminApi.getSkillStats()` | 技能统计 API 封装到 typed API 层 |
| `Record<string, unknown>` → `SkillStats` | 定义 `SkillLiveData`、`SkillHistoricalData`、`SkillStats` 接口 |
| 移除 `as number` 类型断言 | 模板中改用 `??` 运算符，配合强类型不再需要断言 |

### 9.3 类型定义扩展

| 文件 | 变更 |
|------|------|
| `api/types.ts` | `RetrievalConfig` 新增 `llm_model?`、`embedding_model?` 可选字段 |
| `api/admin.ts` | 新增 `SkillLiveData`、`SkillHistoricalData`、`SkillStats` 接口导出 |

### 9.4 测试覆盖扩展

新增 16 个后端测试用例（总计 154 passed）：

| 测试类 | 测试数 | 覆盖模块 |
|--------|--------|----------|
| `TestDocumentParserExtended` | 3 | `parser.py` UTF-8、页面结构、支持格式 |
| `TestChunkerExtended` | 8 | `chunker.py` 中文分句、重叠、最小块合并、表格处理 |
| `TestEmbedderExtended` | 3 | `embedder.py` 批次嵌入、分批处理、维度验证 |

```
后端：154 passed (+16), 覆盖率 64%
前端：64 passed
总计：218 tests all green
```

---

## 十、安全加固与后端修复 (v4.4)

### 10.1 中间件顺序修复

| 修复 | 文件 | 说明 |
|------|------|------|
| ExceptionHandler 位置 | `main.py` | `ExceptionHandlerMiddleware` 移至栈顶（最后添加 → 最先执行），确保能捕获 `RateLimitMiddleware` 等内层中间件的异常 |

**修复前顺序**：RequestTracking → ExceptionHandler → Metrics → RateLimit → CORS
**修复后顺序**：ExceptionHandler → RequestTracking → Metrics → RateLimit → CORS

### 10.2 SQL LIKE 通配符注入修复

| 修复 | 文件 | 说明 |
|------|------|------|
| LIKE 通配符转义 | `api/knowledge.py` | 用户输入中的 `%`、`_`、`\` 在 LIKE 查询前转义，防止通配符改变搜索语义 |

转义逻辑：`q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")` + `ESCAPE '\\'`

### 10.3 模型配置持久化

| 变更 | 文件 | 说明 |
|------|------|------|
| 新增 `llm_model` 字段 | `api/knowledge.py` | `RetrievalConfigUpdate` 模型新增 `llm_model: str?` |
| 新增 `embedding_model` 字段 | `api/knowledge.py` | `RetrievalConfigUpdate` 模型新增 `embedding_model: str?` |
| 数据库 Schema | `init.sql` + `mysql/init.sql` | `retrieval_configs` 表新增 `llm_model`、`embedding_model` 列 |
| Alembic 迁移 | `001_initial_schema.py` | 迁移文件同步更新 |

### 10.4 chat.py 前向引用修复

| 修复 | 文件 | 说明 |
|------|------|------|
| 类定义顺序 | `api/chat.py` | `ChatRequest` 和 `ChatResponse` 移至 `build_initial_state()` 函数之前，修复 `NameError: name 'ChatRequest' is not defined` |

### 10.5 测试覆盖扩展

新增 20 个后端测试用例（总计 174 passed）：

| 测试类 | 测试数 | 覆盖模块 |
|--------|--------|----------|
| `TestLikeWildcardEscaping` | 7 | LIKE 通配符转义逻辑 |
| `TestRetrievalConfigUpdate` | 4 | 配置模型验证 |
| `TestKnowledgeModels` | 4 | 知识库模型验证 |
| `TestMiddlewareOrdering` | 2 | 中间件注册顺序 |
| `TestKnowledgeSearchValidation` | 3 | 搜索请求验证 |

```
后端：174 passed (+20), 覆盖率 64%
前端：64 passed
总计：238 tests all green
```

---

## 十一、覆盖率提升与 Bug 修复 (v4.5)

### 11.1 StreamScrubber 修复

| 修复 | 文件 | 说明 |
|------|------|------|
| 不完整 JSON 阻塞修复 | `core/stream_scrubber.py` | `_process_json()` 对不完整 JSON 不再无限阻塞缓冲区，改为刷新为文本并恢复正常状态 |

### 11.2 chat.py 类定义顺序修复

| 修复 | 文件 | 说明 |
|------|------|------|
| 前向引用 | `api/chat.py` | `ChatRequest`/`ChatResponse` 移至 `build_initial_state()` 之前，修复 `NameError` |

### 11.3 测试覆盖大幅提升

新增 54 个后端测试用例（总计 228 passed），覆盖率从 64% 提升至 67%：

| 测试类 | 测试数 | 覆盖模块 | 覆盖率变化 |
|--------|--------|----------|-----------|
| `TestStreamScrubberExtended` | 12 | `stream_scrubber.py` | 67% → 85%+ |
| `TestContextEngineExtended` | 10 | `context_engine.py` | 74% → 85%+ |
| `TestErrorClassifierExtended` | 9 | `error_classifier.py` | 50% → 80%+ |
| `TestSkillRegistryExtended` | 12 | `registry.py` | 75% → 85%+ |
| `TestRetrieverExtended` | 7 | `retriever.py` | 54% → 70%+ |
| `TestTruncationStrategyEdgeCases` | 2 | `context_engine.py` | — |
| `TestEstimateTokensExtended` | 3 | `context_engine.py` | — |

```
后端：228 passed (+54), 覆盖率 67%
前端：64 passed
总计：292 tests all green
```

## 十二、核心模块覆盖率补齐 (v4.6)

### 12.1 Curator 数据库 Mock 修复

`test_coverage_boost_2.py` 中 Curator 的 `run_maintenance()` 调用 `_prune_stale()` 和 `_consolidate_duplicates()` 时会尝试连接真实数据库导致测试挂起。通过 `patch("app.storage.database.get_db_session")` Mock 数据库会话解决。

### 12.2 测试覆盖持续提升

新增 65 个后端测试用例（总计 293 passed），覆盖率从 67% 提升至 74%：

| 测试类 | 测试数 | 覆盖模块 | 覆盖率变化 |
|--------|--------|----------|-----------|
| `TestMemoryManagerExtended` | 14 | `memory_manager.py` | 53% → 94% |
| `TestCuratorExtended` | 7 | `curator.py` | 22% → 63% |
| `TestAuthExtended` | 10 | `auth.py` | 58% → 74% |
| `TestRedisClientExtended` | 4 | `redis_client.py` | 46% → 52% |
| `TestBuildRagPrompt` | 3 | `answer_agent.py` | 9% → 44% |
| `TestGenerateAnswerExtended` | 2 | `answer_agent.py` | — |
| `TestAnswerNodeExtended` | 2 | `answer_agent.py` | — |
| `TestGraphRouting` | 10 | `graph.py` | 25% → 62% |
| `TestLLMClientExtended` | 5 | `llm_client.py` | 53% → 62% |
| `TestRunAgent` | 2 | `graph.py` | — |
| `TestDocumentParserEdgeCases` | 3 | `parser.py` | 21% → 26% |
| `TestSearchSkillExtended` | 3 | `search_skill.py` | 28% |

```
后端：293 passed (+65), 覆盖率 74%
前端：64 passed
总计：357 tests all green
```

## 十三、实战部署指南 (v4.7)

### 13.1 前置条件

| 依赖 | 版本 | 用途 |
|------|------|------|
| Docker Desktop | 4.x+ | 容器化部署（推荐） |
| Docker Compose | v2+ | 多服务编排 |
| Python | 3.10+ | 后端本地开发 |
| Node.js | 18+ | 前端本地开发 |
| 智谱 AI API Key | — | GLM-4 对话 + Embedding 向量化 |

### 13.2 方式一：Docker Compose 一键启动（推荐）

**适用场景：** 快速体验完整功能，不需要本地安装 MySQL/Redis/Milvus。

**Step 1：创建根目录 .env 文件**

```bash
cd mindpilot

# 从模板创建
cp .env.example .env
```

**编辑 .env，填入以下必填项：**

```bash
# 安全密钥（生成命令：python -c "import secrets; print(secrets.token_urlsafe(64))"）
SECRET_KEY=你的随机密钥

# MySQL
MYSQL_ROOT_PASSWORD=你的root密码
MYSQL_PASSWORD=你的应用密码

# 智谱 AI（必须，去 https://open.bigmodel.cn 获取）
ZHIPU_API_KEY=你的智谱API密钥

# MinIO（对象存储，可保持默认）
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=你的minio密码
```

**Step 2：启动全部服务**

```bash
docker compose up -d
```

**首次启动会拉取以下镜像（约 2-3GB）：**
- `mysql:8.0`
- `redis:7-alpine`
- `milvusdb/milvus:v2.3.4`
- `quay.io/coreos/etcd:v3.5.5`
- `minio/minio`
- `nginx:alpine`
- 后端和前端会本地构建

**Step 3：等待健康检查通过**

```bash
# 查看所有容器状态
docker compose ps

# 等待全部显示 "healthy"（约 1-2 分钟）
# 关键顺序：etcd → minio → milvus → mysql → redis → backend → frontend → nginx
```

**Step 4：访问应用**

| 服务 | 地址 | 说明 |
|------|------|------|
| 应用主页 | http://localhost | Nginx 统一入口 |
| 健康检查 | http://localhost/health | 返回各服务状态 |
| 后端 API | http://localhost:8000 | 仅容器内部网络可访问 |
| API 文档 | http://localhost:8000/docs | 开发时用，生产环境已 deny |

**Step 5：注册账号并使用**

```bash
# 注册（通过 API 或前端页面）
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

然后打开 http://localhost ，登录后即可开始对话。

### 13.3 方式二：本地开发（前后端分离）

**适用场景：** 开发调试，需要热重载。

**Step 1：启动基础设施**

```bash
# 只启动 MySQL、Redis、Milvus（不启动应用服务）
docker compose up -d mysql redis milvus etcd minio
```

**Step 2：配置后端**

```bash
cd mindpilot/backend

# 创建虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（已有 backend/.env，确认以下项）
# ZHIPU_API_KEY=你的密钥
# MYSQL_PASSWORD=你的密码（需与 docker-compose 中 MYSQL_PASSWORD 一致）
```

**Step 3：初始化数据库**

```bash
# MySQL 容器启动后，init.sql 会自动执行建表
# 如果需要手动初始化：
docker exec -i mindpilot-mysql -u mindpilot -p mindpilot < init.sql
```

**Step 4：启动后端**

```bash
cd mindpilot/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 5：启动前端**

```bash
cd mindpilot/frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 13.4 QQ 机器人配置

**前提：** 后端 API 已在 http://localhost:8000 运行。

**Step 1：安装 QQ 客户端适配器**

推荐 [NapCatQQ](https://github.com/NapNeko/NapCatQQ)（基于 NTQQ 的 OneBot 实现）：
1. 下载 NapCatQQ
2. 登录 QQ 号
3. 配置反向 WebSocket：`ws://127.0.0.1:8080/onebot/v11/ws`

**Step 2：配置机器人**

```bash
cd mindpilot/bot

# 安装依赖
pip install nonebot2 nonebot-adapter-onebot httpx zhipuai

# 创建 .env（或在系统环境变量中设置）
```

机器人 .env 内容：
```bash
HOST=127.0.0.1
PORT=8080
API_BASE_URL=http://127.0.0.1:8000
ZHIPU_API_KEY=你的智谱API密钥
SUPERUSERS=["你的QQ号"]
NICKNAME=["MindPilot", "小P"]
```

**Step 3：启动机器人**

```bash
cd mindpilot/bot
python bot.py
```

**Step 4：测试**

在 QQ 中 @机器人 发送消息，或私聊机器人。

### 13.5 常见启动问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `docker compose up` 卡住 | 镜像拉取慢 | 配置 Docker 镜像加速器 |
| Milvus 启动失败 | etcd/minio 未就绪 | 等待 30 秒后重试，或 `docker compose restart milvus` |
| 后端连接 MySQL 失败 | 密码不一致 | 确认 `.env` 中 `MYSQL_PASSWORD` 与 docker-compose 一致 |
| 智谱 API 报错 | Key 过期或余额不足 | 去 https://open.bigmodel.cn 检查 |
| 前端 404 | 后端未启动 | 先确认 `curl http://localhost:8000/health` 有响应 |
| SSE 流式不工作 | Nginx 缓冲 | 确认 nginx.conf 中 `proxy_buffering off` |
| QQ 机器人无响应 | WebSocket 未连接 | 检查 NapCatQQ 反向 WS 配置 |
| 端口冲突 | 3306/6379/80 被占用 | `netstat -ano | findstr :端口号` 查看占用 |

### 13.6 停止与清理

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（会丢失所有数据！）
docker compose down -v

# 只重启某个服务
docker compose restart backend

# 查看日志
docker compose logs -f backend
docker compose logs -f milvus
```

---

*文档版本：v4.7*
*更新时间：2026-05-09*
