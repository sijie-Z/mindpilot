# MindPilot — 多模态智能知识检索与多端协作平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Vue-3.4-4FC08D?style=flat-square&logo=vue.js&logoColor=white" alt="Vue">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-Agent-FF6B6B?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Milvus-2.3-00A3E0?style=flat-square&logo=milvus&logoColor=white" alt="Milvus">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/CI-Pass-brightgreen?style=flat-square" alt="CI">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
</p>

**MindPilot** 是一个企业级 RAG（检索增强生成）平台，支持多模态文档理解、混合检索、多 Agent 协作编排，以及网页 / QQ / 飞书多端接入。

> **核心亮点**: LangGraph 多 Agent 编排 | Self-RAG 自检 | 混合检索 (Vector + BM25 + RRF) | RAGAS 质量评估 | SSE 流式对话 | 多模态理解 | Skill 自动注册与遥测 | 错误分类与恢复 | 注入防护 | 对话分支 | 语义搜索高亮 | RAG 质量仪表盘

---

## 核心能力

| 模块 | 能力 |
|------|------|
| **文档解析** | PDF / Word / PPT / TXT，支持扫描件 PaddleOCR |
| **多模态理解** | 图片问答、截图解析、架构图分析（GLM-4V） |
| **混合检索** | 语义向量 + BM25 关键词 + RRF 融合 + BGE Reranker |
| **多 Agent 编排** | LangGraph 状态机：意图识别 → 检索 → 生成 → RAGAS 评估 |
| **流式对话** | SSE 流式输出 + AbortController 取消，实时展示生成过程 |
| **多端接入** | Vue 3 网页 + QQ 机器人 (NoneBot2) + 飞书机器人 |
| **安全加固** | bcrypt 密码、JWT 认证、DOMPurify XSS 防护、Milvus 注入防护、Prompt 注入扫描 |
| **Skill 自动注册** | 目录扫描自动发现、意图路由、遥测追踪（调用次数/延迟/成功率） |
| **会话全文搜索** | MySQL FULLTEXT + ngram 中文分词，跨会话历史检索 |
| **错误分类** | 结构化 FailoverReason 枚举 + 恢复提示（重试/压缩/降级/轮换凭证） |
| **上下文管理** | 可插拔 ContextEngine + StreamScrubber 防止内部上下文泄漏 |
| **对话分支** | 从任意消息点创建对话分支，分支树可视化，支持切换/删除 |
| **语义搜索高亮** | 句子级相关性评分，基于 Embedding 余弦相似度的精准高亮 |
| **RAG 质量仪表盘** | RAGAS 指标趋势、分数分布、延迟百分位、Token 用量分析 |
| **企业级部署** | Docker Compose 8 服务编排、网络隔离、健康检查、Nginx 安全头 + 限流 |

---

## 技术架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         接入层 (Clients)                          │
│   Vue 3 SPA (Element Plus)  │  QQ Bot (NoneBot2)  │  Feishu Bot  │
└──────────────────────────────────────────────────────────────────┘
                                   │
                        Nginx (反向代理 / SSE)
                                   │
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI 后端 (Port 8000)                     │
│                                                                  │
│   中间件链: RequestID → Exception → Metrics → RateLimit → CORS   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              LangGraph Multi-Agent 编排                   │    │
│   │  IntentAgent → RetrievalAgent → AnswerAgent → EvalAgent  │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│   Skill 系统: 自动注册 + 意图路由 + 遥测追踪 (6个Skill)           │
│                                                                  │
│   RAG Pipeline: Parse → Chunk → Embed → Hybrid Search → Rerank   │
│                                                                  │
│   Agent 模式: ErrorClassifier │ ContextEngine │ StreamScrubber    │
│               InjectionScanner │ MemoryManager │ Curator         │
│                                                                  │
│   企业特性: 滑动窗口限流 │ 去相关抖动重试 │ 熔断器 │ LangFuse 追踪 │
└──────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────────────────────────────────────┐
│                         数据层 (Storage)                          │
│   MySQL 8.0 (元数据+ngram全文索引) │ Milvus 2.3 (向量库) │ Redis 7    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### Docker Compose（推荐）

```bash
git clone <repo-url> && cd mindpilot

# 设置 API Key
export ZHIPU_API_KEY=your-key

# 一键启动全部服务（MySQL + Redis + Milvus + Backend + Frontend）
docker compose up -d

# 查看日志
docker compose logs -f backend
```

访问（Nginx 统一入口，端口 80）:
- 应用: http://localhost
- 健康检查: http://localhost/health

### 本地开发

**环境要求:** Python 3.10+ | Node.js 18+ | MySQL 8.0 | Redis 7 | Milvus 2.3

```bash
# 1. 后端
cd backend
cp .env.example .env   # 编辑填入 ZHIPU_API_KEY 等
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 2. 前端（新终端）
cd frontend
npm install
npm run dev              # → http://localhost:5173
```

### 运行测试

```bash
# 后端测试
cd backend

# 单元测试（无需外部服务）
pytest tests/ -v -m "not integration"

# 全部测试（需要 MySQL + Redis + 后端运行中）
pytest tests/ -v

# 覆盖率报告
pytest tests/ -v --cov=app --cov-report=html

# 前端测试
cd frontend

# 运行所有测试
npm test

# 监听模式
npm run test:watch

# 覆盖率报告
npm run test:coverage

# 测试 UI
npm run test:ui
```

---

## 项目结构

```
mindpilot/
├── backend/
│   ├── app/
│   │   ├── agents/              # LangGraph 多 Agent 编排
│   │   │   ├── graph.py              # Agent 状态图
│   │   │   ├── intent_agent.py       # 意图识别
│   │   │   ├── retrieval_agent.py    # 检索 Agent
│   │   │   ├── answer_agent.py       # 生成 Agent (流式 + Self-RAG)
│   │   │   ├── eval_agent.py         # RAGAS 评估
│   │   │   ├── self_rag.py           # Self-RAG 自检
│   │   │   └── state.py              # AgentState 定义
│   │   ├── api/                 # API 路由
│   │   │   ├── admin.py              # 管理后台 (用户/统计/评估)
│   │   │   ├── analytics.py          # RAG 质量分析 (趋势/分布/延迟)
│   │   │   ├── auth.py               # 认证 (bcrypt + JWT)
│   │   │   ├── branches.py           # 对话分支 CRUD
│   │   │   ├── chat.py               # 对话 + SSE 流式
│   │   │   ├── document.py           # 文档上传 + 后台处理
│   │   │   ├── feishu.py             # 飞书 Webhook
│   │   │   ├── health.py             # 健康检查 + Prometheus
│   │   │   ├── highlight.py          # 语义搜索高亮
│   │   │   ├── image.py              # 图片问答
│   │   │   └── knowledge.py          # 知识库 CRUD
│   │   ├── core/                # 基础设施
│   │   │   ├── exceptions.py         # 统一异常体系
│   │   │   ├── error_classifier.py   # 错误分类 + 恢复提示 (Hermes Agent)
│   │   │   ├── context_engine.py     # 可插拔上下文管理 + 压缩
│   │   │   ├── stream_scrubber.py    # SSE 流式上下文清洗
│   │   │   ├── injection_scanner.py  # Prompt 注入扫描
│   │   │   ├── memory_manager.py     # 记忆管理器 (预取/同步)
│   │   │   ├── curator.py            # RAG 索引维护代理
│   │   │   ├── llm_client.py         # LLM 客户端 (智谱 + 重试)
│   │   │   ├── logger.py             # 结构化日志 (structlog)
│   │   │   ├── metrics.py            # Prometheus 指标
│   │   │   ├── observability.py      # LangFuse 追踪
│   │   │   ├── rate_limit.py         # 滑动窗口限流 (Redis)
│   │   │   ├── retry.py              # 指数退避 + 去相关抖动 + 熔断
│   │   │   └── container.py          # 依赖注入容器
│   │   ├── rag/                 # RAG 管线
│   │   │   ├── parser.py             # 文档解析 (PDF/Word/PPT)
│   │   │   ├── chunker.py            # 文本切片 (语义分块)
│   │   │   ├── embedder.py           # 向量化 (智谱 Embedding-3)
│   │   │   ├── retriever.py          # 混合检索 (Vector + BM25 + RRF)
│   │   │   ├── reranker.py           # BGE Reranker 重排序
│   │   │   ├── vector_store.py       # Milvus 向量库 (HNSW)
│   │   │   └── consistency.py        # 数据一致性 (双写回滚)
│   │   ├── multimodal/          # 多模态
│   │   │   ├── ocr.py                # PaddleOCR
│   │   │   └── vision.py             # GLM-4V 视觉理解
│   │   ├── skills/              # Skill 系统 (自动注册 + 遥测)
│   │   │   ├── base.py               # Skill 基类
│   │   │   ├── registry.py           # 自动发现注册表 + 遥测追踪
│   │   │   ├── calc_skill.py         # 计算器 (calculation 意图)
│   │   │   ├── search_skill.py       # 网络搜索 (search 意图)
│   │   │   ├── rag_skill.py          # RAG 检索 (doc_qa 意图)
│   │   │   ├── image_skill.py        # 图片理解 (image 意图)
│   │   │   ├── code_skill.py         # 代码执行 (code 意图，沙箱)
│   │   │   └── analysis_skill.py     # 数据分析 (analysis 意图，CSV/JSON)
│   │   └── storage/             # 存储
│   │       ├── database.py           # MySQL (aiomysql)
│   │       ├── redis_client.py       # Redis 封装
│   │       ├── models.py             # ORM 模型
│   │       └── session_repo.py       # 会话持久化
│   ├── tests/                   # 测试
│   ├── alembic/                 # 数据库迁移
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_conversation_branches.py
│   ├── Dockerfile               # 多阶段构建 (非 root)
│   ├── init.sql                 # 初始 Schema (bcrypt)
│   ├── pyproject.toml           # pytest + ruff + mypy
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # API 封装
│   │   │   ├── index.ts             # Axios 实例 + 拦截器
│   │   │   ├── types.ts             # 共享类型定义
│   │   │   ├── branches.ts          # 对话分支 API
│   │   │   ├── chat.ts              # SSE 流式 + AbortController
│   │   │   ├── highlight.ts         # 语义高亮 API
│   │   │   ├── knowledge.ts         # 知识库 API
│   │   │   └── admin.ts             # 管理 API
│   │   ├── views/               # 页面
│   │   │   ├── ChatView.vue         # 对话 (SSE 流式)
│   │   │   ├── KnowledgeView.vue    # 知识库列表
│   │   │   ├── KnowledgeDetailView.vue
│   │   │   ├── AdminView.vue        # 管理后台
│   │   │   ├── WorkflowView.vue     # 工作流可视化
│   │   │   └── LoginView.vue
│   │   ├── components/          # 组件
│   │   │   ├── BranchTree.vue        # 分支树面板
│   │   │   ├── BranchIndicator.vue   # 分支点指示器
│   │   │   ├── HighlightedText.vue   # 语义高亮文本
│   │   │   └── QualityDashboard.vue  # RAG 质量仪表盘
│   │   ├── stores/              # Pinia 状态
│   │   │   ├── app.ts               # 全局状态 (清理/媒体查询)
│   │   │   ├── chat.ts              # 对话状态 (SSE + 缓存)
│   │   │   └── knowledge.ts         # 知识库状态
│   │   ├── utils/
│   │   │   └── markdown.ts          # DOMPurify + marked 渲染
│   │   ├── router/
│   │   │   └── index.ts             # Vue Router
│   │   └── __tests__/           # Vitest 单元测试
│   │       ├── setup.ts             # 测试环境配置
│   │       ├── markdown.test.ts     # 工具函数测试
│   │       ├── stores.test.ts       # Store 测试
│   │       ├── router.test.ts       # 路由测试
│   │       ├── api.test.ts          # API 测试
│   │       └── components.test.ts   # 组件测试
│   ├── e2e/                     # Playwright E2E
│   ├── Dockerfile               # 多阶段 (Node + Nginx)
│   ├── nginx.conf               # SPA + SSE 代理
│   ├── vitest.config.ts         # Vitest 配置
│   └── vite.config.ts           # 代码分割 + 代理
├── bot/                         # QQ 机器人
│   ├── bot.py
│   └── plugins/
├── nginx/
│   └── nginx.conf               # 反向代理 + 安全头 + 限流
├── mysql/
│   └── init.sql                 # Docker 初始化脚本
├── docker-compose.yml           # 8 服务编排 (网络隔离)
├── .env.example                 # 环境变量模板
└── README.md
```

---

## API 概览

启动后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档。

| 路由 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/health` | GET | 健康检查（DB + Redis + Milvus） | 无 |
| `/health/metrics` | GET | Prometheus 指标 | 无 |
| `/api/auth/register` | POST | 用户注册 | 无 |
| `/api/auth/login` | POST | 用户登录 | 无 |
| `/api/auth/me` | GET | 当前用户信息 | JWT |
| `/api/chat/` | POST | 非流式对话 | 无 |
| `/api/chat/stream` | POST | SSE 流式对话 | 无 |
| `/api/chat/search` | GET | 会话全文搜索 (ngram) | 无 |
| `/api/document/upload` | POST | 上传文档 | JWT |
| `/api/knowledge/` | GET/POST | 知识库列表 / 创建 | JWT |
| `/api/knowledge/{id}` | GET/PUT/DELETE | 知识库详情 / 更新 / 删除 | JWT |
| `/api/workflow/` | GET | 工作流图 | 无 |
| `/api/workflow/run` | POST | 执行工作流 | 无 |
| `/api/admin/users` | GET/POST | 用户管理 | Admin |
| `/api/admin/stats` | GET | 系统统计 | Admin |
| `/api/admin/evaluations` | GET | 评估记录 | Admin |
| `/api/admin/skill-stats` | GET | 技能使用统计 (实时+历史) | Admin |
| `/api/admin/skill-logs` | GET | 技能执行日志 | Admin |
| `/api/admin/evaluations/summary` | GET | RAG 质量指标汇总 | Admin |
| `/api/branches/create` | POST | 创建对话分支 | JWT |
| `/api/branches/list/{session_id}` | GET | 获取会话分支列表 | JWT |
| `/api/branches/{branch_id}` | GET/DELETE | 分支详情/删除 | JWT |
| `/api/branches/switch` | POST | 切换当前分支 | JWT |
| `/api/highlight/sentences` | POST | 句子级语义评分 | JWT |
| `/api/highlight/chunks` | POST | 批量文本语义高亮 | JWT |
| `/api/analytics/quality/trends` | GET | RAG 质量趋势 | Admin |
| `/api/analytics/quality/distribution` | GET | 质量分数分布 | Admin |
| `/api/analytics/quality/latency` | GET | 延迟百分位统计 | Admin |
| `/api/analytics/tokens/usage` | GET | Token 用量统计 | Admin |
| `/api/feishu/webhook` | POST | 飞书机器人回调 | 签名 |
| `/api/image/chat` | POST | 图片对话 | 无 |

---

## 关键技术选型

| 层 | 技术 | 说明 |
|----|------|------|
| **后端框架** | FastAPI | 异步、自动 OpenAPI、Pydantic 校验 |
| **Agent 编排** | LangGraph | 状态图、条件分支、SSE 状态回传 |
| **LLM** | GLM-4-Flash (Zhipu) | 快速响应，可选 GLM-4-Plus |
| **Embedding** | Zhipu Embedding-3 | 2048 维向量 |
| **向量库** | Milvus 2.3 | 分布式向量检索，HNSW 索引 |
| **全文检索** | MySQL ngram + BM25 | 中文分词，RRF 融合 |
| **Reranker** | BGE Reranker v2 | Cross-encoder 重排序 |
| **OCR** | PaddleOCR | 中英文扫描件识别 |
| **视觉理解** | GLM-4V | 图片问答、图表分析 |
| **缓存** | Redis 7 | 会话缓存、限流计数 |
| **可观测** | LangFuse + Prometheus | 全链路追踪、Token 用量、延迟监控 |
| **Skill 遥测** | 内存追踪 + MySQL 持久化 | 调用次数、成功率、延迟、fire-and-forget 写入 |
| **Agent 模式** | ErrorClassifier + ContextEngine + MemoryManager | 参考 Hermes Agent 的错误分类、上下文压缩、记忆管理 |
| **前端** | Vue 3 + Element Plus + Pinia | Composition API、SSE 流式渲染 |
| **前端测试** | Vitest + Vue Test Utils | 单元测试、覆盖率、UI 测试 |
| **后端测试** | pytest + pytest-cov | 单元测试、集成测试、覆盖率 |
| **构建** | Vite | HMR 开发、Tree-shaking 构建 |
| **CI/CD** | GitHub Actions | 自动 lint、test、build、Docker 构建、Release |
| **对话分支** | branch_id 隔离 + 消息复制 | 任意节点分叉、分支树可视化 |
| **语义高亮** | Embedding 余弦相似度 | 句子级评分、opacity 渐变高亮 |
| **质量仪表盘** | RAGAS 聚合 + 纯 CSS 图表 | 趋势/分布/延迟百分位/Token 分析 |
| **部署** | Docker Compose + Nginx | 多阶段构建、反向代理、SSE 支持 |

---

## License

MIT
