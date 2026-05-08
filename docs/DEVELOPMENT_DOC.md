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

*文档版本：v4.0*
*更新时间：2026-05-09*
