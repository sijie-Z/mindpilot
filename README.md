# MindPilot — 多模态智能知识检索与多端协作平台

**MindPilot** 是一个企业级 RAG（检索增强生成）平台，支持多模态文档理解、混合检索、多 Agent 协作编排，以及网页 / QQ / 飞书多端接入。

---

## 核心能力

| 模块 | 能力 |
|------|------|
| **文档解析** | PDF / Word / PPT / TXT，支持扫描件 PaddleOCR |
| **多模态理解** | 图片问答、截图解析、架构图分析（GLM-4V） |
| **混合检索** | 语义向量 + BM25 关键词 + RRF 融合 + BGE Reranker |
| **多 Agent 编排** | LangGraph 状态机：意图识别 → 检索 → 生成 → RAGAS 评估 |
| **流式对话** | SSE 流式输出，实时展示生成过程 |
| **多端接入** | Vue 3 网页 + QQ 机器人 (NoneBot2) + 飞书机器人 |
| **企业级运维** | 限流、熔断、重试、结构化日志、LangFuse 可观测、Prometheus 指标 |

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
│   Skill 系统: Calculator │ Search │ RAG │ Image Understanding     │
│                                                                  │
│   RAG Pipeline: Parse → Chunk → Embed → Hybrid Search → Rerank   │
│                                                                  │
│   企业特性: 滑动窗口限流 │ 指数退避重试 │ 熔断器 │ LangFuse 追踪  │
└──────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────────────────────────────────────┐
│                         数据层 (Storage)                          │
│   MySQL 8.0 (元数据+全文索引) │ Milvus 2.3 (向量库) │ Redis 7    │
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

访问:
- 前端: http://localhost:3000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

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
cd backend

# 单元测试（无需外部服务）
pytest tests/ -v -m "not integration"

# 全部测试（需要 MySQL + Redis + 后端运行中）
pytest tests/ -v

# 覆盖率报告
pytest tests/ -v --cov=app --cov-report=html
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
│   │   │   ├── answer_agent.py       # 生成 Agent (流式)
│   │   │   ├── eval_agent.py         # RAGAS 评估
│   │   │   ├── self_rag.py           # Self-RAG 自检
│   │   │   └── workflow.py           # 自定义工作流
│   │   ├── api/                 # API 路由
│   │   │   ├── admin.py              # 管理后台 (用户/统计/评估)
│   │   │   ├── auth.py               # 认证 (JWT)
│   │   │   ├── chat.py               # 对话 + SSE 流式
│   │   │   ├── document.py           # 文档上传 + 解析
│   │   │   ├── feishu.py             # 飞书 Webhook
│   │   │   ├── health.py             # 健康检查 + Prometheus
│   │   │   ├── image.py              # 图片问答
│   │   │   ├── knowledge.py          # 知识库 CRUD
│   │   │   └── workflow.py           # 工作流 API
│   │   ├── core/                # 基础设施
│   │   │   ├── exceptions.py         # 统一异常体系
│   │   │   ├── llm_client.py         # LLM 客户端 (GLM-4 + 重试)
│   │   │   ├── logger.py             # 结构化日志 (JSON/Human)
│   │   │   ├── metrics.py            # Prometheus 指标
│   │   │   ├── observability.py      # LangFuse 追踪
│   │   │   ├── rate_limit.py         # 滑动窗口限流 (Redis)
│   │   │   ├── retry.py              # 指数退避 + 熔断
│   │   │   └── container.py          # 依赖注入容器
│   │   ├── rag/                 # RAG 管线
│   │   │   ├── parser.py             # 文档解析 (PDF/Word/PPT)
│   │   │   ├── chunker.py            # 文本切片 (语义分块)
│   │   │   ├── embedder.py           # 向量化 (Zhipu Embedding)
│   │   │   ├── retriever.py          # 混合检索 (Vector + BM25)
│   │   │   ├── reranker.py           # BGE Reranker 重排序
│   │   │   ├── vector_store.py       # Milvus 向量库
│   │   │   ├── faiss_store.py        # FAISS 本地备选
│   │   │   └── consistency.py        # 数据一致性检查
│   │   ├── multimodal/          # 多模态
│   │   │   ├── ocr.py                # PaddleOCR
│   │   │   └── vision.py             # GLM-4V 视觉理解
│   │   ├── skills/              # Skill 系统
│   │   │   ├── base.py               # Skill 基类 + 注册表
│   │   │   ├── calc_skill.py         # 计算器
│   │   │   ├── search_skill.py       # 搜索
│   │   │   ├── rag_skill.py          # RAG 检索
│   │   │   └── image_skill.py        # 图片理解
│   │   └── storage/             # 存储
│   │       ├── database.py           # MySQL (aiomysql)
│   │       ├── redis_client.py       # Redis 封装
│   │       ├── models.py             # ORM 模型
│   │       └── session_repo.py       # 会话持久化
│   ├── tests/                   # 测试 (46+ 单元 + 集成)
│   │   ├── test_agents.py
│   │   ├── test_error_handling.py
│   │   ├── test_flow.py              # 全链路集成测试
│   │   ├── test_logger.py
│   │   ├── test_rag.py
│   │   ├── test_skills_auth.py
│   │   └── test_storage.py
│   ├── alembic/                 # 数据库迁移
│   ├── Dockerfile               # 多阶段构建
│   ├── init.sql                 # 初始 Schema
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/               # 页面
│   │   │   ├── ChatView.vue         # 对话 (SSE 流式)
│   │   │   ├── KnowledgeView.vue    # 知识库列表
│   │   │   ├── KnowledgeDetailView.vue
│   │   │   ├── AdminView.vue        # 管理后台
│   │   │   ├── WorkflowView.vue     # 工作流编辑器
│   │   │   └── LoginView.vue
│   │   ├── components/          # 组件
│   │   ├── stores/              # Pinia 状态
│   │   ├── api/                 # API 封装
│   │   └── composables/         # 组合式函数
│   ├── e2e/                     # Playwright E2E
│   ├── Dockerfile               # 多阶段 (Node + Nginx)
│   └── nginx.conf               # SPA + SSE 代理
├── bot/                         # QQ 机器人
│   ├── bot.py
│   └── plugins/
├── docker-compose.yml           # 8 服务编排
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
| `/api/document/upload` | POST | 上传文档 | JWT |
| `/api/knowledge/` | GET/POST | 知识库列表 / 创建 | JWT |
| `/api/knowledge/{id}` | GET/PUT/DELETE | 知识库详情 / 更新 / 删除 | JWT |
| `/api/workflow/` | GET | 工作流图 | 无 |
| `/api/workflow/run` | POST | 执行工作流 | 无 |
| `/api/admin/users` | GET/POST | 用户管理 | Admin |
| `/api/admin/stats` | GET | 系统统计 | Admin |
| `/api/admin/evaluations` | GET | 评估记录 | Admin |
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
| **前端** | Vue 3 + Element Plus + Pinia | Composition API、SSE 流式渲染 |
| **构建** | Vite | HMR 开发、Tree-shaking 构建 |
| **部署** | Docker Compose + Nginx | 多阶段构建、反向代理、SSE 支持 |

---

## License

MIT
